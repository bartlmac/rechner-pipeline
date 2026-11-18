"""Regression tests for checked-in agent workflow instructions.

Knoten: system/skills
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def test_codex_repo_skills_match_claude_skills() -> None:
    """Codex support must not drift from the verified Claude skill bodies.

    Verglichen werden die VERZEICHNISSE, nicht eine gepflegte Liste. Die
    Liste hier zaehlte neun Paare auf und vergass das vorhandene
    ``transformiere-quellbestand``: eine einseitige Aenderung daran blieb
    gruen, waehrend AGENTS.md die Paritaet als test-erzwungen ausweist.
    Eine Handliste ist genau so lange vollstaendig, bis jemand einen Skill
    hinzufuegt -- und dann sagt sie nichts mehr, ohne rot zu werden.
    """
    claude_wurzel = REPO_ROOT / ".claude" / "skills"
    codex_wurzel = REPO_ROOT / ".agents" / "skills"

    def _dateien(wurzel: Path) -> set:
        return {p.relative_to(wurzel) for p in wurzel.rglob("*") if p.is_file()}

    claude_dateien, codex_dateien = _dateien(claude_wurzel), _dateien(codex_wurzel)
    assert claude_dateien, "keine Skills gefunden — Pfad falsch?"
    nur_claude = sorted(str(p) for p in claude_dateien - codex_dateien)
    nur_codex = sorted(str(p) for p in codex_dateien - claude_dateien)
    assert not nur_claude, f"nur unter .claude/skills/: {nur_claude}"
    assert not nur_codex, f"nur unter .agents/skills/: {nur_codex}"

    unterschiedlich = sorted(
        str(rel) for rel in claude_dateien
        if (claude_wurzel / rel).read_bytes() != (codex_wurzel / rel).read_bytes()
    )
    assert not unterschiedlich, f"Inhalt weicht ab: {unterschiedlich}"


def test_root_agents_md_documents_codex_without_breaking_claude() -> None:
    text = _read("AGENTS.md")
    assert ".agents/skills/" in text
    assert ".claude/skills/" in text
    assert "codex exec --cd . --sandbox workspace-write" in text
    assert "Do not use RPC calls" in text




def test_migrations_skills_nennen_die_tragenden_regeln() -> None:
    """Das Stage-1-Know-how ist versioniertes Repo-Artefakt, kein
    Session-Prompt: die Kernregeln muessen im Skill stehen."""
    extraktion = _read(".claude/skills/extrahiere-quellfragment/SKILL.md")
    assert "GENAU EINE Quelle" in extraktion
    assert "nicht_belegt" in extraktion
    assert "model_json_schema" in extraktion          # Schema generiert, nie kopiert
    assert "KEINE Vorschrift" in extraktion           # unisex-Regel
    runbook = _read(".claude/skills/migrationsfall-durchfuehren/SKILL.md")
    # Vorlaeufige Aufloesung ist ein Kommando (--vorlaeufig), kein Skript
    # (U1, Z1-06) — der Skill muss den Weg nennen.
    assert "--vorlaeufig" in runbook and "--akteur" in runbook
    assert "gate_entscheid" in runbook
    assert "STOPP" in runbook                         # Abbruchkriterien
    # Kein Test auf den NAMEN des Referenzfalls mehr. Er zeigte auf
    # `faelle/`, einen gitignorierten Datenraum (ADR-002) — der Test
    # konnte also nie pruefen, ob es den Fall gibt, sondern nur, ob eine
    # Zeichenkette dasteht. Als der Fall umbenannt wurde, hielt er die
    # veraltete Angabe fest, statt sie zu melden: ein Test, der einen
    # Fehler konserviert. Was der Runbook-Text ueber den Referenzfall
    # sagt, gehoert in den Skill, nicht in eine Wortliste.


def test_rollen_skills_tragen_ihre_haerte_grenzen() -> None:
    """Die Skill-Architektur lebt: jeder Rollen-Skill traegt Auftrag UND
    Grenze; die nicht verhandelbaren Kerne sind festgehalten."""
    entwickler = _read(".claude/skills/entwickle-im-zielsystem/SKILL.md")
    assert "NICHT verhandelbar" in entwickler
    assert "Schichtenkarte" in entwickler
    assert "Knoten-Annotation" in entwickler
    assert "Don't ship without tests" in entwickler
    assert "STOPP-Kriterien" in entwickler
    tester = _read(".claude/skills/teste-adversarial/SKILL.md")
    assert "WIDERLEGT" in tester
    assert "Mutations-Denken" in tester
    assert "f(x)==f(x)" in tester
    doku = _read(".claude/skills/dokumentiere-system/SKILL.md")
    assert "Generiert schlaegt handgeschrieben" in doku
    assert "EIN Zuhause" in doku
    konflikt = _read(".claude/skills/bereite-fachkonflikt-auf/SKILL.md")
    assert "du entscheidest NICHT" in konflikt
    assert "vorlaeufig=True" in konflikt
    assert "Auswirkungsanalyse" in konflikt
    controlling = _read(
        ".claude/skills/pruefe-migrationscontrolling/SKILL.md"
    )
    assert "du rechnest NIE selbst" in controlling
    assert "A-M4" in controlling
    assert "NIE" in controlling and "aufgeweicht" in controlling  # Toleranzen
    aktuartest = _read(".claude/skills/aktuartest-durchfuehren/SKILL.md")
    assert "du rechnest NIE selbst" in aktuartest
    assert "A-M1" in aktuartest
    assert "NIE" in aktuartest and "aufgeweicht" in aktuartest
    assert "Golden-Master-Tests" in aktuartest             # Ausbaustufe festgehalten
    assert "Stichprobe" in aktuartest
    ci = _read(".claude/skills/integriere-migrationsinkrement/SKILL.md")
    assert "ADR-007" in ci
    assert "Branch je INKREMENT" in ci
    assert "Push macht der Mensch" in ci
    assert "git add -A" in ci
    # Rollen-Katalog und Skills bleiben synchron:
    katalog = _read("docs/architektur/skill-architektur.md")
    for skill in (REPO_ROOT / ".claude" / "skills").glob("*/SKILL.md"):
        name = skill.parent.name
        assert name in katalog, name
        assert (REPO_ROOT / ".agents" / "skills" / name / "SKILL.md").is_file(), name


# --------------------------------------------------------------------------- #
# Agentenrollen des KI-Tools (ADR-018, Schritt 2)
# --------------------------------------------------------------------------- #

AGENTENROLLEN = ("aktuariat", "architektur", "rechenkern", "programmleitung", "betrieb")


def test_agentenrollen_sind_in_beiden_baeumen_byte_identisch() -> None:
    """Dieselbe Paritaet wie bei den Skills: Verzeichnisse, keine Liste."""
    claude_wurzel = REPO_ROOT / ".claude" / "agents"
    codex_wurzel = REPO_ROOT / ".agents" / "agents"
    claude = {p.name for p in claude_wurzel.glob("*.md")}
    codex = {p.name for p in codex_wurzel.glob("*.md")}
    assert claude == codex == {f"{n}.md" for n in AGENTENROLLEN}
    for name in claude:
        assert (claude_wurzel / name).read_bytes() == (codex_wurzel / name).read_bytes(), name


def test_jede_agentenrolle_nennt_kennung_gegenstueck_und_zeichnungsverbot() -> None:
    """Eine Agentenrolle ohne ihre Kennung, ohne menschliches Gegenstueck
    oder ohne das Zeichnungsverbot waere eine Rolle ohne Ebene — genau
    die Unschaerfe, die T20/U1 fanden."""
    import re

    skills = {p.name for p in (REPO_ROOT / ".claude" / "skills").iterdir() if p.is_dir()}
    for name in AGENTENROLLEN:
        text = (REPO_ROOT / ".claude" / "agents" / f"{name}.md").read_text(encoding="utf-8")
        assert text.startswith("---\n") and f"\nname: {name}\n" in text
        assert f"agent/{name}" in text, name
        assert "mensch/" in text and "zeichnet" in text, name
        assert "zeichnest nie" in text, name
        # Jeder genannte Skill existiert.
        for skill in re.findall(r"``([a-z-]+)``", text):
            if skill in ("nicht_belegt", "mehrdeutig", "widerspruechlich"):
                continue
            if "-" in skill:
                assert skill in skills, f"{name}: Skill {skill!r} gibt es nicht"


def _bericht_aufrufe(text: str) -> list[str]:
    """Jeder Aufruf von ``bestand.cli_report`` im Text, als ein Befehl: die
    Fortsetzungszeilen (Zeilenende ``\\``) zusammengezogen, bei einem Aufruf in
    einer Zeile nur der Rest der Zeile bis zum Ende des Codespans."""
    aufrufe = []
    zeilen = text.splitlines()
    for i, zeile in enumerate(zeilen):
        if "bestand.cli_report" not in zeile:
            continue
        befehl = zeile
        while befehl.rstrip().endswith("\\") and i + 1 < len(zeilen):
            i += 1
            befehl = befehl.rstrip()[:-1] + " " + zeilen[i]
        aufrufe.append(befehl)
    return aufrufe


def test_skill_bericht_aufrufe_nennen_den_lauf_des_stamms() -> None:
    """Runde E, Nachbesserung (Befund 3): ``cli_report`` weist einen Stamm
    ohne ``--historie``/``--ledger`` ab, sobald eine Nebentabelle daneben
    liegt — und neben dem Stamm der Uebernahme (``bestand.parquet``) liegen
    Historie und Ledger immer. Ein dokumentierter Aufruf ohne Journal waere
    ein Aufruf, der im echten Verzeichnis mit Exit 2 endet. Mechanik: jeder
    Aufruf in einem Skill traegt beide Flags. Mutationsprobe: die Flags aus
    dem VOR-Bericht streichen -> rot."""
    gesehen = 0
    for skill in sorted((REPO_ROOT / ".claude" / "skills").rglob("*.md")):
        for befehl in _bericht_aufrufe(skill.read_text(encoding="utf-8")):
            gesehen += 1
            assert "--historie" in befehl and "--ledger" in befehl, (skill.parent.name, befehl)
    assert gesehen >= 2          # Positivkontrolle: der Scanner findet die Aufrufe


def test_skill_bericht_scanner_findet_einen_aufruf_ohne_journal() -> None:
    ohne = "python -m rechner_pipeline.bestand.cli_report --portfolio <bestand>.parquet --out x.html"
    mit = ("python -m rechner_pipeline.bestand.cli_report \\\n    --portfolio a.parquet \\\n"
           "    --historie h.parquet \\\n    --ledger l.parquet \\\n    --out x.html")
    assert [("--historie" in b and "--ledger" in b) for b in _bericht_aufrufe(ohne)] == [False]
    assert [("--historie" in b and "--ledger" in b) for b in _bericht_aufrufe(mit)] == [True]


def _fehlende_markdown_referenzen(wurzel: Path) -> list[str]:
    """Relative Dokumentlinks pruefen, auch wenn Details ausgelagert sind."""
    import re

    fehlend = []
    for datei in wurzel.rglob("*.md"):
        for ziel in re.findall(r"\[[^\]]*\]\(([^)]+)\)", datei.read_text(encoding="utf-8")):
            if "://" in ziel:
                continue
            pfad, _, anker = ziel.partition("#")
            zieldatei = datei.parent / pfad if pfad else datei
            if not zieldatei.is_file():
                fehlend.append(f"{datei.relative_to(wurzel)} -> {ziel}")
            elif anker:
                inhalt = zieldatei.read_text(encoding="utf-8")
                explizite_anker = re.findall(r'<a id="([^"]+)"></a>', inhalt)
                if explizite_anker.count(anker) != 1:
                    fehlend.append(f"{datei.relative_to(wurzel)} -> {ziel}")
    return fehlend


def test_skill_referenzen_existieren_auch_nach_aufteilung() -> None:
    assert not _fehlende_markdown_referenzen(REPO_ROOT / ".claude" / "skills")


def test_referenzscanner_findet_fehlende_unterdatei(tmp_path: Path) -> None:
    """Negativkontrolle: ein guter Einstieg darf keine verlorene Referenz verdecken."""
    (tmp_path / "SKILL.md").write_text("[Phase](references/fehlt.md)", encoding="utf-8")
    assert _fehlende_markdown_referenzen(tmp_path) == ["SKILL.md -> references/fehlt.md"]


def test_referenzscanner_erkennt_fehlenden_und_doppelten_abschnitt(tmp_path: Path) -> None:
    (tmp_path / "SKILL.md").write_text("[Phase](detail.md#phase)", encoding="utf-8")
    ziel = tmp_path / "detail.md"
    ziel.write_text("# Andere Phase", encoding="utf-8")
    assert _fehlende_markdown_referenzen(tmp_path) == ["SKILL.md -> detail.md#phase"]
    ziel.write_text('<a id="phase"></a>\n# Phase', encoding="utf-8")
    assert _fehlende_markdown_referenzen(tmp_path) == []
    ziel.write_text('<a id="phase"></a>\n<a id="phase"></a>', encoding="utf-8")
    assert _fehlende_markdown_referenzen(tmp_path) == ["SKILL.md -> detail.md#phase"]


def test_referenzscanner_prueft_dateiinterne_anker(tmp_path: Path) -> None:
    datei = tmp_path / "SKILL.md"
    datei.write_text("[Phase](#phase)", encoding="utf-8")
    assert _fehlende_markdown_referenzen(tmp_path) == ["SKILL.md -> #phase"]
    datei.write_text('[Phase](#phase)\n<a id="phase"></a>', encoding="utf-8")
    assert _fehlende_markdown_referenzen(tmp_path) == []


def test_fallskill_kern_und_phasen_referenzen_sind_verknuepft() -> None:
    wurzel = REPO_ROOT / ".claude" / "skills" / "migrationsfall-durchfuehren"
    kern = (wurzel / "SKILL.md").read_text(encoding="utf-8")
    assert len(kern.splitlines()) < 500
    for name in ("quellen-und-transformation", "spezifikation-und-parametrierung",
                 "abnahmen-und-berichte", "betriebsuebergabe"):
        assert f"references/{name}.md" in kern
        phase = (wurzel / "references" / f"{name}.md").read_text(encoding="utf-8")
        assert "ablauf-detail.md" in phase
    detail = (wurzel / "references" / "ablauf-detail.md").read_text(encoding="utf-8")
    for abschnitt in ("Stufe 0b", "Stufe 1b", "Gate A-Q1", "Stufe 2",
                      "Stufe 3b", "Gate A-M4", "Fallabbruch"):
        assert abschnitt in detail
    assert "A-M6" in kern and "A-M5" in kern and "GENAU EINE Quelle" in kern
    assert "Sperre niemals umgehen" in kern


def test_native_adapter_verweisen_auf_die_gemeinsamen_fuenf_rollen() -> None:
    """Format-/Verweisnachweis, ausdruecklich keine native Hostausfuehrung."""
    import tomllib

    codex = REPO_ROOT / ".codex" / "agents"
    opencode = REPO_ROOT / ".opencode" / "agents"
    assert {p.stem for p in codex.glob("*.toml")} == set(AGENTENROLLEN)
    assert {p.stem for p in opencode.glob("*.md")} == set(AGENTENROLLEN)
    for rolle in AGENTENROLLEN:
        profil = tomllib.loads((codex / f"{rolle}.toml").read_text(encoding="utf-8"))
        assert set(profil) == {"name", "description", "developer_instructions"}
        assert profil["name"] == rolle and profil["description"]
        verweis = f".agents/agents/{rolle}.md"
        assert verweis in profil["developer_instructions"]
        assert (REPO_ROOT / verweis).is_file()
        text = (opencode / f"{rolle}.md").read_text(encoding="utf-8")
        assert text.startswith("---\ndescription:") and verweis in text
        modus = "primary" if rolle == "programmleitung" else "subagent"
        assert f"\nmode: {modus}\n" in text
        assert "nicht technisch vor" in text


def test_rollen_werkzeugprofile_haben_skillzugang_und_nur_pl_delegation() -> None:
    """Expliziter Claude-Profilnachweis; Host kann Rechte weiterhin begrenzen."""
    for rolle in AGENTENROLLEN:
        text = _read(f".claude/agents/{rolle}.md")
        kopf = text.split("---", 2)[1]
        werkzeuge = next(z for z in kopf.splitlines() if z.startswith("tools: "))
        namen = {n.strip() for n in werkzeuge[len("tools: "):].split(",")}
        assert "Skill" in namen, rolle
        assert ("Agent" in namen) == (rolle == "programmleitung"), rolle
        assert "ADR-032" in text, rolle


def test_stufe_1b_bestandsbericht_ist_vom_a_m4_berichtspaar_getrennt() -> None:
    """C1: Der separate Stufe-1b-Bestandsbericht (``--berichtsstichtag``
    nach ``abgeleitet/bestand-nach/bestandsbericht.html``) blieb bei der
    Aufteilung des Fallskills als vollstaendiger Aufruf verloren. Er steht
    jetzt als EIGENER Aufruf beim Owner der Fortschreibung
    (fuehrung-und-berichtspaar.md, Anker ``fortschreibung``) und wird nicht
    mit dem A-M4-Berichtspaar vermischt, dessen VOR-/NACH-Aufrufe ueber
    ``--bis`` laufen. Mutationsprobe: ``--berichtsstichtag`` oder die
    Zieldatei ``bestandsbericht.html`` aus der Referenz streichen -> rot;
    den Stufe-1b-Aufruf als NACH-Bericht umbiegen -> rot."""
    referenz = _read(
        ".claude/skills/pruefe-migrationscontrolling/references/"
        "fuehrung-und-berichtspaar.md"
    )
    _pruefe_stufe_1b_bericht(referenz)


def _pruefe_stufe_1b_bericht(referenz: str) -> None:
    """Historische Flag/Wert-Paare am selben Aufruf, nicht in Begleitprosa."""
    import shlex

    aufrufe = _bericht_aufrufe(referenz)
    stufe_1b = [b for b in aufrufe if "--berichtsstichtag" in b]
    assert len(stufe_1b) == 1, aufrufe
    tokens = shlex.split(stufe_1b[0])
    erwartet = {
        "--portfolio": "faelle/<fall>/abgeleitet/bestand-nach/bestand_gesamt.parquet",
        "--historie": "faelle/<fall>/abgeleitet/bestand-nach/historie.parquet",
        "--ledger": "faelle/<fall>/abgeleitet/bestand-nach/ledger.parquet",
        "--scheiben": "faelle/<fall>/abgeleitet/bestand-nach/scheiben.parquet",
        "--merkmale": "faelle/<fall>/abgeleitet/bestand/merkmale.parquet",
        "--config": "<bestand-config>.toml",
        "--berichtsstichtag": "<migrationsstichtag>",
        "--out": "faelle/<fall>/abgeleitet/bestand-nach/bestandsbericht.html",
    }
    for flag, wert in erwartet.items():
        assert tokens.count(flag) == 1, flag
        index = tokens.index(flag)
        assert tokens[index + 1:index + 2] == [wert], (flag, tokens)
    assert "--bis" not in stufe_1b[0]                  # beide Schalter = Fehler
    paare = [b for b in aufrufe if "--bis" in b]
    assert len(paare) >= 2, aufrufe                    # VOR und NACH des Paars
    assert all("--berichtsstichtag" not in b for b in paare)


def test_stufe_1b_ratsche_erkennt_falsche_werte_trotz_richtiger_prosa() -> None:
    """Jedes falsche Flag/Wert-Paar muss trotz historischer Pfade in Prosa rot sein."""
    import re
    import pytest

    referenz = _read(".claude/skills/pruefe-migrationscontrolling/references/"
                     "fuehrung-und-berichtspaar.md")
    befehl = next(b for b in _bericht_aufrufe(referenz) if "--berichtsstichtag" in b)
    block = next(b for b in referenz.split("```")
                 if "python -m rechner_pipeline.bestand.cli_report" in b
                 and "--berichtsstichtag" in b)
    for flag in ("--out", "--berichtsstichtag", "--portfolio", "--historie",
                 "--ledger", "--scheiben", "--merkmale", "--config"):
        muster = re.compile(re.escape(flag) + r"\s+(\S+)")
        richtig = muster.search(befehl).group(1)
        falsch = referenz.replace(block, muster.sub(flag + " falsch", block, count=1), 1)
        falsch += "\nHistorischer Wert nur in Prosa: " + richtig
        with pytest.raises(AssertionError):
            _pruefe_stufe_1b_bericht(falsch)


def test_widerspruch_im_manifest_regel_lebt_nur_im_schicht_owner() -> None:
    """I1: Die normative Fallback-Regel des Schichtbelegs ("Widersprechen
    sich Manifest und Datei ... neu erzeugen, statt die Datei zu umgehen")
    hat GENAU EIN Zuhause: die Fachreferenz schicht-und-pflichtmengen.md.
    Der aktuartest-Skill darf sie nicht noch einmal vollstaendig duplizieren,
    er nennt nur Pflicht und Verweis. Mutationsprobe: den vollen Wortlaut
    wieder in den Skill zurueckschreiben -> rot."""
    fundstellen = []
    for datei in (REPO_ROOT / ".claude" / "skills").rglob("*.md"):
        if "Widersprechen sich Manifest" in datei.read_text(encoding="utf-8"):
            fundstellen.append(datei.relative_to(REPO_ROOT).as_posix())
    assert fundstellen == [
        ".claude/skills/aktuartest-durchfuehren/references/schicht-und-pflichtmengen.md"
    ]
    aktuartest = _read(".claude/skills/aktuartest-durchfuehren/SKILL.md")
    assert "schicht-und-pflichtmengen.md" in aktuartest      # Verweis bleibt


def test_betriebsrouter_laesst_das_zugangsverfahren_im_owner() -> None:
    """I1: Der Betriebsrouter (betriebsuebergabe.md) haelt nur Vorbedingungen
    und Sequenz fest; das vollstaendige Zugangsverfahren (Kommando mit
    ``--zeichnungsordnung`` und Freigabering ``--freigabe-schluessel``)
    liegt ausschliesslich im Owner-Skill uebernehme-migrationsbestand.
    Mutationsprobe: den vollen Aufruf wieder in den Router kopieren -> rot."""
    router = _read(".claude/skills/migrationsfall-durchfuehren/references/"
                   "betriebsuebergabe.md")
    owner = _read(".claude/skills/uebernehme-migrationsbestand/SKILL.md")
    assert "--zeichnungsordnung" in owner and "--freigabe-schluessel" in owner
    assert "python -m rechner_pipeline.betrieb.zugangsprobe" not in router
    assert "--freigabe-schluessel" not in router
    # Die Sequenz mit dem menschlichen Gate bleibt am Router.
    assert "A-B2" in router and "Zugangsprobe" in router


def test_abnahmebericht_kommando_lebt_nur_im_controlling_owner() -> None:
    """I1: Das Abnahmebericht-Kommando (erkennbar am Flag
    ``--bestandsbericht-vor``) steht GENAU EINMAL als vollstaendiger Aufruf:
    in der Fachreferenz fuehrung-und-berichtspaar.md (Anker
    ``abnahmebericht``). Weder der Controlling-Skill noch der
    Abnahmen-Phasenverfahren-Router tragen eine zweite vollstaendige
    Regeldefinition, sie verweisen. Mutationsprobe: das Kommando wieder in
    den Skill kopieren -> rot."""
    fundstellen = []
    for datei in (REPO_ROOT / ".claude" / "skills").rglob("*.md"):
        if "--bestandsbericht-vor" in datei.read_text(encoding="utf-8"):
            fundstellen.append(datei.relative_to(REPO_ROOT).as_posix())
    assert fundstellen == [
        ".claude/skills/pruefe-migrationscontrolling/references/"
        "fuehrung-und-berichtspaar.md"
    ]
    controlling = _read(".claude/skills/pruefe-migrationscontrolling/SKILL.md")
    assert "fuehrung-und-berichtspaar.md" in controlling


def test_fallskill_ladeanweisung_nennt_die_normativen_phasenverfahren() -> None:
    """I4: Die Ladeanweisung des Fallskills nennt die normativen
    Phasenverfahren/Fachreferenzen; der Kompatibilitaetsindex ablauf-detail.md
    ist kein Pflichtverfahren mehr. Die alte Formulierung "Abschnitte der
    Detailreferenz" (Router -> Vollkopie) ist entfernt."""
    kern = _read(".claude/skills/migrationsfall-durchfuehren/SKILL.md")
    assert "Abschnitte der Detailreferenz" not in kern
    assert "ablauf-detail.md" in kern
    assert "kein Pflichtverfahren" in kern
    for name in ("quellen-und-transformation", "spezifikation-und-parametrierung",
                 "abnahmen-und-berichte", "betriebsuebergabe"):
        assert f"references/{name}.md" in kern


def test_kompatindex_schichtanker_verweist_auf_die_fachreferenz() -> None:
    """M3: Der alte Kompatibilitaetsanker ``schichtbeleg`` fuehrt zum
    tatsaechlichen Anker der Fachreferenz (``#schichtbeleg``), nicht nur zur
    Datei — dann loest der Ankerverweistest auch gegen die Fachreferenz auf."""
    detail = _read(".claude/skills/migrationsfall-durchfuehren/references/"
                   "ablauf-detail.md")
    assert "schicht-und-pflichtmengen.md#schichtbeleg" in detail
    ziel = _read(".claude/skills/aktuartest-durchfuehren/references/"
                 "schicht-und-pflichtmengen.md")
    assert '<a id="schichtbeleg"></a>' in ziel
