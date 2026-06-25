# Offene Follow-ups nach dem main-Merge (Stand 2026-06-25)

Bewusst **offen** gehalten (nicht geschlossen). Kein Merge-Blocker — der Merge
`feat/anthropic-provider -> main` (`72b9647`) ist erfolgt. Reihenfolge grob nach
Dringlichkeit. Erledigtes ist als solches markiert, bleibt aber als Spur stehen.

## Erledigt im Zuge des Merges

- [x] **Review-Findings F1–F4** behoben (Commit `3ba3e1e`, Tests; CR-002 §9).
- [x] **fs_confine gehärtet** (Commit `72941a8`): Laufzeit-Block für
  `subprocess`/`os.system`/`os.popen`/`socket` als Defense-in-depth zu F1.
- [x] **Lokale Alt-Branches gelöscht** (`feat/anthropic-provider`, `alex_1`,
  `refactor/structure` — alle vollständig in `main`).

## Offen — Bartek (Git/GitHub, extern)

- [ ] **`main` pushen.** Lokales `main` liegt ~50 Commits vor `origin/main`;
  `origin/main` ist unverändert. Push macht ausschließlich Bartek.
- [ ] **GitHub-PR #3 klären.** Basis war `alex_1` (nicht Default-Branch `main`),
  kein `Closes`-Keyword. Nach dem Push: PR schließen, Issues (#1, #4) ggf.
  manuell schließen.
- [ ] **Remote-Branches aufräumen.** `origin/feat/anthropic-provider`,
  `origin/alex_1`, `origin/refactor/structure` erst nach PR-#3-Klärung
  entfernen (Löschen von `origin/alex_1` würde PR #3 auto-schließen).

## Offen — Validierung / Plattform

- [ ] **1 bezahlter End-to-End-Verifikationslauf**, in dem der generierte
  Rechenkern `golden_master_outputs()` real implementiert und der feste Harness
  echtes Pass/Fail liefert (bisher offline/synthetisch verifiziert) — CR-002 §8.
- [ ] **Contract `golden_master_outputs()` final mit Alexander bestätigen**
  (Prompt-/Test-/Compare-Stufe = seine Domäne) — CR-002 §6/§8.
- [ ] **Windows-Re-Verifikation** des Default-Pfads (bisher nur Linux empirisch)
  — Merge-Vorbedingung zu Issue #1.

## Offen — Infrastruktur / Governance (CRs)

- [ ] **CR-004 — echte OS-Sandbox** (Container `--network none` + read-only
  Mounts). Die robustere Form der fs_confine-Defense-in-depth; In-Process-
  Monkeypatch bleibt grundsätzlich umgehbar.
- [ ] **CR-003 — CI-Matrix** (Linux/macOS/Windows × Python 3.11–3.13);
  `.github/workflows/ci.yml` noch nicht angelegt. Sichert u. a. den
  fs_confine-Pfad auf Windows ab.
- [ ] **requires-python 3.12 -> 3.11** an Alexander + Team kommunizieren (im Code
  erledigt, Begründung/Kommunikation offen) — läuft über den Wissens-Graph.
- [ ] **CR-005 — Modell-Eskalation** (Sonnet -> Opus) + Mess-Protokoll; nur nach
  Budget-Freigabe (kostet API).
- [ ] **CR-001 — Auth/Billing** (API-Key vs. Abo/Agent SDK) im Team vertiefen;
  Token-/Kosten-Skalierung breiter betrachten.
- [ ] **Sicherheits-Review der geänderten geteilten Module** durch Alexander:
  `qa/fs_confine.py` (F1-Härtung) und der fixed-Modus-Scan in `runner.py`
  berühren seine Domäne (dev/README „Don't touch without discussion").

## Offen — kleinere Backlog-Punkte

- [ ] `dossier._options_dict()` langfristig auf `dataclasses.fields()` umstellen,
  damit die Allowlist nicht beim nächsten Options-Feld erneut veraltet.
- [ ] Echte Läufe in einen separaten, nicht automatisch aufräumbaren Pfad legen
  (`runs/real/<stamp>/`) — Schutz vor versehentlichem Löschen.
- [ ] Demo-Log: bei gekürzten Listen „… und weitere X von Y" ausgeben.
