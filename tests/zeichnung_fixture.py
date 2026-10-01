"""Zeichnungsordnung und Schluessel fuer Tests — nach ADR-018.

Eine Annahme braucht seit ADR-018 eine Zeichnungsordnung (Schema 2) und
einen Schluessel, aus dem die Rolle BESTIMMT wird. Dieser Helfer legt
beides je Testfall an: eine simulierte Rolle ``mensch/aktuariat``
(Schluesselklasse ``simulation``) und optional weitere Rollen.

Die Rolle zeichnet die Gates des Falls (:data:`FALL_GATES`), NICHT die des
Betriebs (A-B1, A-B2): Ein Schluessel, der Migrations- und Betriebsabnahmen
zugleich zeichnet, verdeckte genau den Fall, den die Rollenregel der Leser
prueft (Entscheid 2026-10-01; Ratsche in tests/test_abnahme_rolle_klasse.py).
Wer A-B1 zeichnet, legt die Ordnung mit ``rolle="mensch/betrieb"`` an.

Ebenso wenig zeichnet sie den Kernstand: A-K2 gehoert ``mensch/rechenkern``
(ADR-018), mit eigenem Schluessel neben dem Fall (``p9-rechenkern.key``).
Jede Standardordnung fuehrt diese Rolle mit; :func:`annahme_args` legt
beide Schluessel in den Ring — A-M4 prueft die Signatur der A-K2-Annahme,
auf der es gruendet —, und :func:`zeichne_kernstand` legt den Kernstand
eines Falls vor und zeichnet ihn (Entscheid des Maintainers 2026-10-01:
jeder Fall traegt sein A-K2). :func:`zeichne_tboxstand` tut dasselbe fuer
den T-Box-Stand (A-O1, mensch/architektur), sobald die Versionslinie der
T-Box einen Uebergang hat; :func:`zeichne_stand` zeichnet beides.

Knoten: system/entscheid
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional

VA = "mensch/aktuariat"
QUELLE = "mensch/quell-aktuar"
AGENT = "agent/programmleitung"
RECHENKERN = "mensch/rechenkern"
ARCHITEKTUR = "mensch/architektur"

_STANDARD_SCHLUESSEL = b"test-only-p9-authorization-key!" * 2
#: Der Schluessel der Rolle mensch/rechenkern — getrennt je Rolle.
_RECHENKERN_SCHLUESSEL = b"test-only-p9-rechenkern-key-ak2!" * 2
#: Der Schluessel der Rolle mensch/architektur (A-O1) — getrennt je Rolle.
_ARCHITEKTUR_SCHLUESSEL = b"test-only-p9-architektur-key-o1!" * 2
#: Dateinamen der getrennten Schluessel neben dem Fall.
RECHENKERN_SCHLUESSEL_DATEI = "p9-rechenkern.key"
ARCHITEKTUR_SCHLUESSEL_DATEI = "p9-architektur.key"
#: Die Gates der Rollen der Standabnahme (models.standabnahme): je Gate eine
#: eigene Rolle mit eigenem Schluessel — Rolle, Gate, Schluesseldatei, Inhalt.
STANDROLLEN = (
    (RECHENKERN, "A-K2", RECHENKERN_SCHLUESSEL_DATEI, _RECHENKERN_SCHLUESSEL),
    (ARCHITEKTUR, "A-O1", ARCHITEKTUR_SCHLUESSEL_DATEI, _ARCHITEKTUR_SCHLUESSEL),
)
RECHENKERN_GATES = ["A-K2"]
#: Die Wurzelrolle der Ordnungslinie (ADR-025) — die Kennung steht an EINER
#: Stelle (``models.ordnungslinie.WURZELROLLE``); eigener Schluessel.
#: Derselbe Schluessel wie der des Vorstands der Test-Ordnung des Betriebs
#: (``freigabe_testschluessel.VORSTANDKEY``): EINE Wurzel je Testlinie, die mit
#: der Ordnung des Betriebs beginnt und die Ordnung des Falls als Glied anhaengt.
from tests.freigabe_testschluessel import VORSTANDKEY as _VORSTAND_SCHLUESSEL  # noqa: E402
VORSTAND_SCHLUESSEL_DATEI = "p9-vorstand.key"
#: Die Programmleitung des Falls (ADR-026): eigener Schluessel, NICHT in der
#: Ordnung — der Fallauftrag benennt sie und gibt ihr das Recht auf A-M5.
_PROGRAMMLEITUNG_SCHLUESSEL = b"test-only-p9-programmleitung-am5" * 2
PROGRAMMLEITUNG_SCHLUESSEL_DATEI = "p9-programmleitung.key"
#: Das Repo, auf dessen Systemstand die Helfer zeichnen.
_REPO = Path(__file__).resolve().parents[1]


def _fall_gates() -> List[str]:
    from rechner_pipeline.models.ordnungslinie import WURZEL_GATES
    from rechner_pipeline.models.zeichnung import FALLROLLEN_GATES, GUELTIGE_GATES

    eigene = {gate for _, gate, _, _ in STANDROLLEN}
    # Den Fallauftrag zeichnet der Vorstand, den Abbruch die Programmleitung
    # mit dem Recht aus dem Auftrag (ADR-026) — nie die Standardrolle.
    return [g for g in GUELTIGE_GATES
            if g not in ("A-B1", "A-B2", "A-B3") and g not in eigene
            and g not in WURZEL_GATES and g not in FALLROLLEN_GATES]


#: Die Gates der Standardrolle (mensch/aktuariat): alle zeichenbaren ausser
#: denen des Betriebs (A-B1, A-B2, A-B3) und der Standabnahme von Kern und
#: T-Box (A-K2, A-O1). Das Tarifwerk (A-T1) zeichnet sie selbst: Es gehoert
#: dem Aktuariat (ADR-025).
FALL_GATES: List[str] = _fall_gates()


def schluessel_anlegen(pfad: Path, inhalt: bytes = _STANDARD_SCHLUESSEL) -> str:
    """Schluesseldatei (0600) anlegen; Rueckgabe: Fingerabdruck."""
    if not pfad.exists():
        pfad.write_bytes(inhalt)
        pfad.chmod(0o600)
    return hashlib.sha256(pfad.read_bytes()).hexdigest()


def ordnung_schreiben(pfad: Path, rollen: Dict[str, dict]) -> Path:
    pfad.write_text(json.dumps({"schema_version": 2, "rollen": rollen}),
                    encoding="utf-8")
    return pfad


def standard_ordnung(
    verzeichnis: Path,
    schluessel: Path,
    *,
    klasse: str = "simulation",
    rolle: str = VA,
    gates: Optional[List[str]] = None,
    weitere: Optional[Dict[str, dict]] = None,
) -> Path:
    """Ordnung mit einer zeichnenden Rolle fuer diesen Schluessel — und der
    Rolle mensch/rechenkern mit ihrem eigenen Schluessel daneben."""
    fp = schluessel_anlegen(schluessel)
    rollen = {rolle: {"schluessel_sha256": fp, "schluesselklasse": klasse,
                      "gates": gates if gates is not None else list(FALL_GATES)}}
    for name, gate, datei, inhalt in STANDROLLEN:
        if rolle == name:
            continue
        eigener_fp = schluessel_anlegen(schluessel.parent / datei, inhalt)
        if eigener_fp != fp:
            rollen[name] = {"schluessel_sha256": eigener_fp, "schluesselklasse": klasse,
                            "gates": [gate]}
    # Die Wurzelrolle steht in jeder Standardordnung (ADR-025, ADR-026): Sie
    # beauftragt jeden Fall und traegt die Ordnungslinie.
    if rolle != _wurzelrolle():
        rollen.update(vorstand_rolle(schluessel.parent))
    rollen.update(weitere or {})
    return ordnung_schreiben(verzeichnis / "zeichnungsordnung.json", rollen)


def _wurzelrolle() -> str:
    from rechner_pipeline.models.ordnungslinie import WURZELROLLE

    return WURZELROLLE


def annahme_args(fall: Path, **kw) -> List[str]:
    """``--zeichnungsordnung ... --freigabe-schluessel ...`` fuer einen Fall.

    Ordnung und Schluessel liegen NEBEN dem Fall (ausserhalb, wie es die
    Ordnung verlangt), je Fall genau einmal angelegt.
    """
    fuer = kw.pop("fuer", None)
    ohne_auftrag = kw.pop("ohne_auftrag", False)
    ohne_linie = kw.pop("ohne_linie", False)
    schluessel = fall.parent / "p9-freigabe.key"
    ordnung = kw.pop("ordnung_pfad", None) or fall.parent / "zeichnungsordnung.json"
    if not ordnung.exists():
        standard_ordnung(fall.parent, schluessel, **kw)
    # Die Linie ist Pflicht (ADR-025, Nachtrag 2026-10-01): Jeder Fall der
    # Suite zeichnet und liest unter der Linie neben ihm, deren Spitze die
    # Ordnung dieses Aufrufs ist — der Normalweg der Suite ist der MIT Wurzel.
    linie = None if ohne_linie else linie_sicherstellen(fall, ordnung)
    # Jeder Abnahmepunkt eines Falls setzt den gezeichneten Fallauftrag voraus
    # (ADR-026): Der gemeinsame Weg beauftragt den Fall, bevor er zeichnet —
    # und neu, sobald sich die Lieferung geaendert hat.
    if not ohne_auftrag and fuer != "A-M6" and (fall / "eingang.json").is_file() \
            and not _auftrag_gilt(fall):
        # Nicht streng: Ein Test, der einen kaputten Fall baut (Scope, Eingang),
        # bekommt die Meldung des Gates zu SEINEM Befund, nicht die des Helfers;
        # fehlt der Auftrag dann, sagt das Gate "kein Fallauftrag".
        fallauftrag_zeichnen(fall, streng=False,
                             **{k: v for k, v in kw.items() if k == "klasse"})
    # Der Ring: alle Schluessel, der zeichnende zuletzt. A-K2 zeichnet
    # mensch/rechenkern, A-O1 mensch/architektur, A-M6 der Vorstand, A-M5 die
    # Programmleitung, jedes andere Gate die Standardrolle. Jede Annahme
    # prueft mit dem Ring die Signaturen der Annahmen, auf denen sie gruendet —
    # den Fallauftrag immer (HMAC-Grenze, ADR-026).
    eigene = {gate: fall.parent / datei for _, gate, datei, _ in STANDROLLEN}
    eigene["A-M6"] = fall.parent / VORSTAND_SCHLUESSEL_DATEI
    eigene["A-M5"] = fall.parent / PROGRAMMLEITUNG_SCHLUESSEL_DATEI
    zeichnend = eigene.get(fuer, schluessel)
    ring = [d for d in [*eigene.values(), schluessel] if d.exists() and d != zeichnend]
    if zeichnend.exists():
        ring.append(zeichnend)
    args = ["--zeichnungsordnung", str(ordnung)]
    if linie is not None and fall.resolve() != linie.resolve():
        args += ["--linie", str(linie)]
    for datei in ring:
        args += ["--freigabe-schluessel", str(datei)]
    # Eine simulierte Rolle handelt unter einem Mandat — Pflicht seit
    # Review T22-07 (ADR-018): das Mandat liegt wie die Ordnung neben dem Fall.
    # Vorstand und Programmleitung sind in der Suite immer simuliert.
    if kw.get("klasse", "simulation") == "simulation" or fuer in ("A-M6", "A-M5"):
        args += ["--mandat", str(mandat_datei(fall))]
    return args


def auftrag_args(fall: Path, ordnung: Optional[Path] = None) -> List[str]:
    """Fuer Tests mit eigenem Argumentbau: den Fall beauftragen, falls noch
    nicht (ADR-026), und die Schluessel von Vorstand und Programmleitung fuer
    den Ring — VOR den zeichnenden Schluessel setzen (der letzte zeichnet).
    Jede Annahme prueft die Signatur des Fallauftrags (HMAC-Grenze).

    ``ordnung``: die eigene Ordnung des Tests; sie bekommt die Wurzelrolle,
    falls ihr die fehlt, wird Spitze der Linie neben dem Fall (die Linie ist
    Pflicht, ADR-025), und unter ihr wird beauftragt. Rueckgabe beginnt mit
    ``--linie <linie>``."""
    ordnung = Path(ordnung) if ordnung is not None else fall.parent / "zeichnungsordnung.json"
    if not ordnung.exists():
        standard_ordnung(fall.parent, fall.parent / "p9-freigabe.key")
    _wurzel_sicherstellen(ordnung, fall.parent)
    linie = linie_sicherstellen(fall, ordnung)
    if (fall / "eingang.json").is_file() and not _auftrag_gilt(fall):
        fallauftrag_zeichnen(fall, streng=False, ordnung_pfad=ordnung)
    return ["--linie", str(linie)] + [
        teil for datei in (VORSTAND_SCHLUESSEL_DATEI, PROGRAMMLEITUNG_SCHLUESSEL_DATEI)
        if (fall.parent / datei).exists()
        for teil in ("--freigabe-schluessel", str(fall.parent / datei))]


def entscheide_args(fall: Path, **kw) -> List[str]:
    """Ordnung, Schluessel und Mandat fuer das Diskrepanz-Kommando
    (``ontologie.entscheide``): Es ist kein Gate, kennt weder ``--linie`` noch
    den Fallauftrag (ADR-026 betrifft die Abnahmepunkte)."""
    return annahme_args(fall, ohne_linie=True, ohne_auftrag=True, **kw)


def linie_args(fall: Path, ordnung: Optional[Path] = None) -> List[str]:
    """``--linie <linie>`` fuer Aufrufe mit eigenem Argumentbau, die nur die
    Linie brauchen (Ablehnungen, Verweigerungen vor dem Schluessel): Ohne
    Linie wird nicht entschieden (ADR-025, Nachtrag 2026-10-01)."""
    fall = Path(fall)
    ordnung = Path(ordnung) if ordnung is not None else fall.parent / "zeichnungsordnung.json"
    if not ordnung.exists():
        standard_ordnung(fall.parent, fall.parent / "p9-freigabe.key")
    return ["--linie", str(linie_sicherstellen(fall, ordnung))]


def linie_sicherstellen(fall: Path, ordnung: Path) -> Path:
    """Die Linie neben dem Fall, mit ``ordnung`` als Spitze (ADR-025).

    Fehlt die Linie, wird sie angelegt und die Ordnung ihr erstes Glied; ist
    die Spitze eine andere Ordnung, haengt der Vorstand die neue als Glied an
    (Schluessel neben dem Fall) — wie im Betrieb: Gezeichnet wird nur unter
    der Spitze. Eine Ordnung, die nicht in die Linie darf (Stern, Rolle des
    Falls oder des abgebenden Hauses), scheitert hier mit der Meldung der
    Linie."""
    from rechner_pipeline.gates import stand_belegen
    from rechner_pipeline.models import ordnungslinie as ol

    linie = fall.parent / "linie"
    if fall.resolve() == linie.resolve():
        return linie
    from tests.freigabe_testschluessel import suitelinie_anlegen

    _wurzel_sicherstellen(Path(ordnung), fall.parent)
    schluessel_anlegen(fall.parent / VORSTAND_SCHLUESSEL_DATEI, _VORSTAND_SCHLUESSEL)
    if not (linie / "linie.json").is_file():
        # Die Test-Linie beginnt mit der Ordnung des Betriebs (deterministisches
        # erstes Glied): Was der Betrieb liest, ist in JEDER Linie der Suite
        # lokalisierbar; die Ordnung des Falls haengt der Vorstand an.
        suitelinie_anlegen(linie)
    # Der Helfer sucht nur die Spitze (Aufbau der Testwelt); gruenden tun die
    # Kommandos, die er ruft — sie lesen die Linie mit dem Ring.
    glieder, fehler = ol.lade_linie_strukturell_zur_anzeige(linie)
    assert not fehler, fehler
    sha = hashlib.sha256(Path(ordnung).read_bytes()).hexdigest()
    if glieder and glieder[-1]["ordnung_sha256"] == sha:
        return linie
    # Ohne --eingetragen-am: die Uhr des Aufrufs (Pruefrunde H). Ein fester
    # Zeitpunkt in der Vergangenheit datierte das Glied VOR Zeichnungen, die
    # schon unter seinem Vorgaenger liegen, und die Zeitregel der Leser
    # verweigerte sie. Die Erklaerung je geminderter Rolle setzt der Helfer
    # ausdruecklich auf "gueltig": Die Suite braucht frueher Gezeichnetes weiter.
    argv = ["ordnung", "--linie", str(linie), "--ordnung", str(ordnung),
            *erklaerung_args(glieder, Path(ordnung), "gueltig")]
    if glieder:
        argv += ["--vorgaenger", glieder[-1]["glied_sha256"],
                 "--vorstand-schluessel", str(fall.parent / VORSTAND_SCHLUESSEL_DATEI)]
    else:
        argv += ["--vorgaenger", "keiner"]
    ergebnis = stand_belegen.main(argv)
    assert ergebnis.exit_code == 0, ergebnis.errors
    return linie


def erklaerung_args(glieder: List[dict], ordnung: Path, erklaerung: str) -> List[str]:
    """``--fruehere-zeichnungen <rolle>=<erklaerung>`` fuer jede Rolle, die das
    Anhaengen von ``ordnung`` an die Spitze von ``glieder`` MINDERT (Pruefrunde
    H). Ausdruecklich je Aufruf gesetzt — der Produktivcode kennt keine
    Vorgabe."""
    from rechner_pipeline.models import ordnungslinie as ol

    vorher = ol.ordnung_aus(glieder[-1]) if glieder else None
    neu = json.loads(Path(ordnung).read_text(encoding="utf-8"))
    return [teil for rolle in ol.geminderte_rollen(ol.aenderungen(vorher, neu))
            for teil in ("--fruehere-zeichnungen", f"{rolle}={erklaerung}")]


def _auftrag_gilt(fall: Path) -> bool:
    """Ob der Fall einen geltenden, angenommenen Fallauftrag auf der heutigen
    Lieferung traegt (strukturell — das Gate prueft Signatur und Rolle)."""
    from rechner_pipeline.gates.stand_belegen import geltende_spitze

    spitze, _ = geltende_spitze(fall, "A-M6")
    if spitze is None or spitze.get("entscheid") != "angenommen":
        return False
    return all(spitze["artefakt_hashes"].get(name)
               == hashlib.sha256((fall / name).read_bytes()).hexdigest()
               for name in ("eingang.json", "fall.json"))


def fallauftrag_zeichnen(fall: Path, *, programmleitung_klasse: str = "simulation",
                         auftrag: str = "Fall der Suite: migrieren und abnehmen",
                         streng: bool = True, ordnung_pfad: Optional[Path] = None, **kw):
    """Den Fall beauftragen (ADR-026): Vorlage legen, als Vorstand A-M6 zeichnen.

    Die Programmleitung bekommt ihren eigenen Schluessel neben dem Fall (nicht
    in der Ordnung), jede simulierte Rolle das Mandat der Suite. Der gemeinsame
    Weg fuer jeden Fall, statt je Test."""
    from rechner_pipeline.gates import fall_belegen, gate_entscheid

    ordnung_pfad = Path(ordnung_pfad or fall.parent / "zeichnungsordnung.json")
    if not ordnung_pfad.exists():
        standard_ordnung(fall.parent, fall.parent / "p9-freigabe.key", **kw)
    ordnung = _wurzel_sicherstellen(ordnung_pfad, fall.parent)
    pl = fall.parent / PROGRAMMLEITUNG_SCHLUESSEL_DATEI
    schluessel_anlegen(pl, _PROGRAMMLEITUNG_SCHLUESSEL)
    argv = ["auftrag", "--fall", str(fall), "--zeichnungsordnung", str(ordnung_pfad),
            "--programmleitung-schluessel", str(pl),
            "--programmleitung-klasse", programmleitung_klasse, "--auftrag", auftrag]
    for rolle in fall_belegen.mandatsrollen(ordnung, programmleitung_klasse):
        argv += ["--mandat", f"{rolle}={mandat_datei(fall)}"]
    # Die Linie ist Pflicht (ADR-025): Der Auftrag verweist auf ihre Abnahmen.
    argv += ["--linie", str(linie_sicherstellen(fall, ordnung_pfad))]
    vorlage = fall_belegen.main(argv)
    if not streng and vorlage.exit_code != 0:
        return vorlage
    assert vorlage.exit_code == 0, vorlage.errors
    ergebnis = gate_entscheid.main([
        "--fall", str(fall), "--gate", "A-M6", "--entscheid", "angenommen",
        "--entscheider", "vorstand", "--begruendung", "Fall beauftragt (Suite)",
        "--repo-root", str(_REPO),
        *annahme_args(fall, fuer="A-M6", ordnung_pfad=ordnung_pfad, **kw)])
    assert not streng or ergebnis.exit_code == 0, ergebnis.errors
    return ergebnis


def _wurzel_sicherstellen(ordnung_pfad: Path, schluessel_ort: Path) -> dict:
    """Eine Testordnung ohne Wurzel bekommt sie, bevor der Fall beauftragt
    wird (ADR-025, ADR-026); Rueckgabe: die Ordnung."""
    ordnung = json.loads(ordnung_pfad.read_text(encoding="utf-8"))
    if _wurzelrolle() not in ordnung["rollen"]:
        ordnung["rollen"].update(vorstand_rolle(schluessel_ort))
        ordnung_schreiben(ordnung_pfad, ordnung["rollen"])
    return ordnung


def mandat_datei(fall: Path) -> Path:
    """Das Mandatsdokument der simulierten Rolle dieses Falls (einmal angelegt)."""
    mandat = fall.parent / "mandat.md"
    if not mandat.exists():
        mandat.write_text(
            "Mandat der Vorzeige: die simulierte Rolle prueft die Vorlagen "
            "und zeichnet die Gates dieses Falls.\n", encoding="utf-8")
    return mandat


def zeichne_kernstand(fall: Path, repo_root: Path, *, von: str = "HEAD", **kw):
    """Den Kernstand eines Falls vorlegen und als mensch/rechenkern zeichnen.

    ``von`` = der zuletzt abgenommene Kernstand; in der Suite ``HEAD`` — der
    Kern des lebenden Stands gilt als abgenommen, der Beleg sagt "nichts
    geaendert" (oder nennt, was im Arbeitsbaum offen ist). Der gemeinsame
    Weg fuer jeden Test, der A-M4 zeichnet (Entscheid 2026-10-01), statt
    je Test. Setzt eine A-Box und P-Q3 voraus wie jede Annahme.
    """
    from rechner_pipeline.gates import gate_entscheid, kernstand_belegen

    beleg = kernstand_belegen.main([
        "--fall", str(fall), "--repo-root", str(repo_root), "--von", von,
        "--begruendung", "Kernstand des Falls (Suite)"])
    assert beleg.exit_code == 0, beleg.errors
    ergebnis = gate_entscheid.main([
        "--fall", str(fall), "--gate", "A-K2", "--entscheid", "angenommen",
        "--entscheider", "rechenkern-verantwortung",
        "--begruendung", "Aenderungen am Kernstand qualitativ geprueft",
        "--repo-root", str(repo_root), *annahme_args(fall, fuer="A-K2", **kw)])
    assert ergebnis.exit_code == 0, ergebnis.errors
    return ergebnis


def zeichne_tboxstand(fall: Path, repo_root: Path, **kw):
    """Den T-Box-Stand eines Falls vorlegen und als mensch/architektur zeichnen.

    Das Gegenstueck zu :func:`zeichne_kernstand` fuer den zweiten Gegenstand
    der Standabnahme (``models.standabnahme``): Hat die Versionslinie der
    T-Box einen Uebergang (seit 0.2.0), verlangt A-M4 je Fall ein A-O1 —
    der Beleg kommt vom Produzenten (``gates.stand_belegen tbox``), die
    Stellungnahme legt (simuliert) das Aktuariat. Alles wird LEBEND
    gerechnet: Modul-Hash, Versionen, Artefakt-Hash; ein Vermerk im Fall
    dient als Artefakt, damit keine Datei des Repos festgeschrieben ist.
    """
    import json

    from rechner_pipeline.gates import gate_entscheid, stand_belegen
    from rechner_pipeline.ontologie import tbox

    vermerk = fall / "abgeleitet" / "tbox" / "vermerk-suite.md"
    vermerk.parent.mkdir(parents=True, exist_ok=True)
    vermerk.write_text(
        f"Aenderungsvermerk der Suite: T-Box {tbox.TBOX_VERSIONEN[-2]} -> "
        f"{tbox.TBOX_VERSION}.\n", encoding="utf-8")
    beleg = stand_belegen.main([
        "tbox", "--fall", str(fall), "--vorher-linie", linie_args(fall)[1],
        "--repo-root", str(repo_root),
        "--artefakt", "abgeleitet/tbox/vermerk-suite.md",
        "--begruendung", "T-Box-Stand des Falls (Suite)"])
    assert beleg.exit_code == 0, beleg.errors
    (fall / stand_belegen.TBOX_STELLUNGNAHME_RELATIV).write_text(json.dumps({
        "schema_version": 1, "nach_version": tbox.TBOX_VERSION,
        "verfasser_rolle": "mensch/aktuariat",
        "felder": [{"name": "tarifwerk", "wirkung": "bewertungsrelevant",
                    "begruendung": "Tarifwerk der Generation als belegte Aussage (Suite)"}],
    }), encoding="utf-8")
    ergebnis = gate_entscheid.main([
        "--fall", str(fall), "--gate", "A-O1", "--entscheid", "angenommen",
        "--entscheider", "it-verantwortung",
        "--begruendung", "Diffs der T-Box geprueft (Suite)",
        "--repo-root", str(repo_root), *annahme_args(fall, fuer="A-O1", **kw)])
    assert ergebnis.exit_code == 0, ergebnis.errors
    return ergebnis


def zeichne_tarifwerk(fall: Path, repo_root: Path, *, von: str = "HEAD", **kw):
    """Das Tarifwerk eines Falls vorlegen und als mensch/aktuariat zeichnen
    (A-T1, ADR-025) — die Standardrolle der Suite IST mensch/aktuariat.
    ``von`` = der zuletzt abgenommene Stand; in der Suite ``HEAD``."""
    from rechner_pipeline.gates import gate_entscheid, tarifwerk_belegen

    beleg = tarifwerk_belegen.main([
        "--fall", str(fall), "--repo-root", str(repo_root), "--von", von,
        "--begruendung", "Tarifwerk des Falls (Suite)"])
    assert beleg.exit_code == 0, beleg.errors
    args = annahme_args(fall, **kw)
    # Die Standardrolle IST mensch/aktuariat; ihr Schluessel ist der, den die
    # Ordnung neben dem Fall ihr gibt — manche Tests legen sie mit einem
    # eigenen Schluessel an (nicht p9-freigabe.key).
    ordnung = json.loads((fall.parent / "zeichnungsordnung.json").read_text(encoding="utf-8"))
    fp = (ordnung["rollen"].get(VA) or {}).get("schluessel_sha256")
    for datei in sorted(fall.parent.glob("*.key")):
        if hashlib.sha256(datei.read_bytes()).hexdigest() == fp:
            args += ["--freigabe-schluessel", str(datei)]
            break
    ergebnis = gate_entscheid.main([
        "--fall", str(fall), "--gate", "A-T1", "--entscheid", "angenommen",
        "--entscheider", "aktuariat",
        "--begruendung", "Tarifplaene und Generationen geprueft (Suite)",
        "--repo-root", str(repo_root), *args])
    assert ergebnis.exit_code == 0, ergebnis.errors
    return ergebnis


def zeichne_stand(fall: Path, repo_root: Path, **kw):
    """Den ganzen Stand eines Falls zeichnen: T-Box-Stand (A-O1), Tarifwerk
    (A-T1) und Kernstand (A-K2). Der gemeinsame Weg fuer jeden Test, der A-M4
    zeichnet."""
    zeichne_tboxstand(fall, repo_root, **kw)
    zeichne_tarifwerk(fall, repo_root, **kw)
    return zeichne_kernstand(fall, repo_root, **kw)


def vorstand_rolle(verzeichnis: Path) -> Dict[str, dict]:
    """Die Wurzelrolle der Ordnungslinie mit ihrem eigenen Schluessel."""
    from rechner_pipeline.models.ordnungslinie import WURZELROLLE, WURZEL_GATES

    fp = schluessel_anlegen(verzeichnis / VORSTAND_SCHLUESSEL_DATEI, _VORSTAND_SCHLUESSEL)
    return {WURZELROLLE: {"schluessel_sha256": fp, "schluesselklasse": "simulation",
                          "gates": list(WURZEL_GATES)}}


def linie_anlegen(verzeichnis: Path, **kw) -> Path:
    """Den Linienbereich ``<verzeichnis>/linie`` anlegen und die Standardordnung
    (mit der Wurzelrolle) als erstes Glied seiner Ordnungslinie eintragen.

    VOR jeder Zeichnung aufrufen: Danach zeichnet jeder Aufruf ueber
    :func:`annahme_args` unter der Spitze der Linie und pinnt ihr Glied."""
    from rechner_pipeline.gates import stand_belegen

    verzeichnis.mkdir(parents=True, exist_ok=True)
    linie = verzeichnis / "linie"
    weitere = dict(kw.pop("weitere", None) or {})
    ordnung = standard_ordnung(verzeichnis, verzeichnis / "p9-freigabe.key",
                               weitere=weitere, **kw)
    assert stand_belegen.main(["linie", "--linie", str(linie)]).exit_code == 0
    ergebnis = stand_belegen.main([
        "ordnung", "--linie", str(linie), "--ordnung", str(ordnung),
        "--vorgaenger", "keiner", "--eingetragen-am", "2026-10-01T08:00:00+00:00"])
    assert ergebnis.exit_code == 0, ergebnis.errors
    return linie


def handbeleg_sicht_nachziehen(bereich: Path, gate: str) -> None:
    """Fuer Tests, die einen Beleg VON HAND an den festen Ort schreiben (statt
    ueber den Produzenten): daneben legen, was der Produzent mitschreibt — die
    Sicht, erzeugt aus genau diesen Bytes ueber das Register
    ``gates.sichten`` (dieselbe Renderfunktion wie Produzent und Gate), und
    fuer A-O1 die Archivkopie des Belegs. Das Gate zeichnet eine Annahme nur,
    wenn beides zum gepinnten Beleg gehoert (Runde G, ADR-025 Nachtrag).

    Kein Weg an der Regel vorbei: Was hier entsteht, ist byte-gleich das, was
    der Produzent schriebe; Tests, deren Gegenstand die Sicht ist, benutzen
    den Produzenten (tests/test_sicht_beleg_ausfall.py)."""
    from rechner_pipeline.gates import sichten, stand_belegen
    from rechner_pipeline.gates._common import schreibe_exklusiv

    eintrag = sichten.SICHTEN[gate]
    belege = {}
    for rolle, relativ in eintrag.belege:
        roh = (Path(bereich) / relativ).read_bytes()
        belege[rolle] = json.loads(roh)
        if eintrag.archiv is not None and eintrag.archiv[0] == rolle:
            archiv = Path(bereich) / stand_belegen.TBOX_ARCHIV_RELATIV
            archiv.mkdir(parents=True, exist_ok=True)
            ziel = archiv / f"{hashlib.sha256(roh).hexdigest()}.json"
            if not ziel.exists():
                schreibe_exklusiv(ziel, roh)
    sicht = Path(bereich) / eintrag.sicht_relativ
    sicht.parent.mkdir(parents=True, exist_ok=True)
    sicht.write_text(eintrag.rendere(belege), encoding="utf-8")
