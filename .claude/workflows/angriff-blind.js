export const meta = {
  name: 'angriff-blind',
  description: 'Blinder Angriff auf einen Bereich (Skill teste-adversarial): je Methode ein unabhaengiger Pruefer, je Finding ein Widerleger',
  whenToUse: 'Kalibrierung vor dem Fix und Angriff nach dem Fix einer Pruefrunde; args: {repo, scratch, gegenstand, zusagen, verboten, linsen:[{key, methode}]}',
  phases: [{ title: 'Finden', detail: 'je Methode ein Pruefer' }, { title: 'Verifizieren', detail: 'je Finding ein Widerleger' }],
}

// Vorlage aus dem Skill teste-adversarial. Alles Fachliche kommt ueber args:
//   repo       absoluter Repo-Pfad
//   scratch    Ablage der Pruefer, JE RUNDE ein eigener Ordner
//   gegenstand Bereich, Module, Einstiege fuer eine synthetische Welt
//   zusagen    die fachlichen Zusagen, gegen die gemessen wird
//   verboten   Dateien, die der Pruefer NICHT lesen darf (Befundliste,
//              eigene Tests der Runde) — sonst ist der Angriff nicht blind
//   linsen     [{key, methode}] — je Methode ein Pruefer (siehe Skill)
// Modell und Aufwand sind ausdruecklich gesetzt, nicht geerbt.
const REPO = args.repo
const SCRATCH = args.scratch
const VERBOTEN = args.verboten || ''

const GEMEINSAM = `Du bist ein unabhaengiger Pruefer (Auftrag: PRUEFUNG, keine Reparatur) fuer das Repo ${REPO} (Interpreter ${REPO}/.venv/bin/python, aus dem Repo-Root).

HARTE REGELN:
- Keine Aenderung an Dateien unter ${REPO}. Deine Dateien und Welten liegen unter deinem Scratch-Verzeichnis.
- NICHT lesen: ${REPO}/docs-local, ${REPO}/simulation, ${REPO}/regie, ${REPO}/faelle; dazu: ${VERBOTEN}. Du pruefst blind.
- KEIN pytest — baue eigene Skripte.
- Nur messen: je Finding ein lauffaehiges Repro-Skript mit Ist, Soll und Positivkontrolle. Eine Sollrechnung ist nur unabhaengig, wenn sie NICHT dieselbe Funktion ruft wie der Ist-Wert.
- Nichts gefunden: leere Liste und was du geprueft hast. Ein erfundenes Finding ist schlimmer als keines.

GEGENSTAND: ${args.gegenstand}

ZUSAGEN, GEGEN DIE GEMESSEN WIRD: ${args.zusagen}

Methode: .claude/skills/teste-adversarial/SKILL.md lesen und anwenden.

AUSGABE: strukturiert. Je Finding: titel; ort; methode; ist; soll; differenz; repro_pfad; positivkontrolle; schwere (hoch|mittel|niedrig). Dazu geprueft: Liste der Pruefungen (auch ohne Fund).`

const LINSEN = (args.linsen || []).map(l => ({
  key: l.key,
  prompt: `${GEMEINSAM}\n\nDEIN SCRATCH: ${SCRATCH}/${l.key}\n\nDEINE METHODE: ${l.methode}`,
}))

const FINDINGS_SCHEMA = {
  type: 'object',
  properties: {
    findings: { type: 'array', items: { type: 'object', properties: {
      titel: { type: 'string' }, ort: { type: 'string' }, methode: { type: 'string' },
      ist: { type: 'string' }, soll: { type: 'string' }, differenz: { type: 'string' },
      repro_pfad: { type: 'string' }, positivkontrolle: { type: 'string' },
      schwere: { type: 'string', enum: ['hoch', 'mittel', 'niedrig'] },
    }, required: ['titel', 'ort', 'methode', 'ist', 'soll', 'differenz', 'repro_pfad', 'positivkontrolle', 'schwere'] } },
    geprueft: { type: 'array', items: { type: 'string' } },
  },
  required: ['findings', 'geprueft'],
}
const VERDICT_SCHEMA = {
  type: 'object',
  properties: { bestaetigt: { type: 'boolean' }, begruendung: { type: 'string' }, korrigierte_zahlen: { type: 'string' }, unabhaengig: { type: 'boolean' } },
  required: ['bestaetigt', 'begruendung', 'unabhaengig'],
}
const MAX_VERIFY = 8

const ergebnisse = await pipeline(
  LINSEN,
  l => agent(l.prompt, { label: `finden:${l.key}`, phase: 'Finden', schema: FINDINGS_SCHEMA, model: 'opus', effort: 'high' }),
  async (res, l) => {
    if (!res) return { linse: l.key, findings: [], geprueft: [], verifiziert: [] }
    const alle = res.findings || []
    if (alle.length > MAX_VERIFY) log(`${l.key}: ${alle.length} Findings, nur die ersten ${MAX_VERIFY} werden verifiziert`)
    const teil = alle.slice(0, MAX_VERIFY)
    const verdicts = await parallel(teil.map(f => () =>
      agent(`Du bist ein unabhaengiger Widerleger. Versuche, dieses Finding zu WIDERLEGEN; im Zweifel bestaetigt=false.

Repo: ${REPO} (Interpreter ${REPO}/.venv/bin/python, aus dem Repo-Root). Keine Aenderung an Dateien unter ${REPO}; nicht lesen: docs-local, simulation, regie, faelle, ${VERBOTEN}. KEIN pytest.

FINDING:
Titel: ${f.titel}
Ort: ${f.ort}
Methode: ${f.methode}
Ist: ${f.ist}
Soll: ${f.soll}
Differenz: ${f.differenz}
Positivkontrolle: ${f.positivkontrolle}
Repro-Skript: ${f.repro_pfad}

AUFGABE: (1) Fuehre das Repro-Skript aus und pruefe, ob es den behaupteten Zustand zeigt. (2) Lies das Skript: Ist die Stoerung realistisch und die Positivkontrolle echt? Wird ein Pruefergebnis durch ein Mock ersetzt oder eine Signatur gefaelscht (dann nicht bestaetigt)? (3) Pruefe die Fundstelle im Code und die zitierten Vertraege. (4) Antworte strukturiert: bestaetigt, begruendung (mit gemessenen Zahlen), unabhaengig, korrigierte_zahlen falls abweichend.`,
        { label: `widerlegen:${l.key}:${f.titel.slice(0, 40)}`, phase: 'Verifizieren', schema: VERDICT_SCHEMA, model: 'opus', effort: 'high' })
        .then(v => ({ ...f, verdict: v }))
    ))
    return { linse: l.key, findings: alle, geprueft: res.geprueft || [], verifiziert: verdicts.filter(Boolean) }
  },
)
const out = ergebnisse.filter(Boolean)
const bestaetigt = out.flatMap(e => e.verifiziert.filter(v => v.verdict && v.verdict.bestaetigt))
log(`Angriff: ${out.reduce((n, e) => n + e.findings.length, 0)} Findings gemeldet, ${bestaetigt.length} bestaetigt`)
return { linsen: out, bestaetigt: bestaetigt.map(v => ({ linse: v.linse, titel: v.titel, ort: v.ort, ist: v.ist, soll: v.soll, differenz: v.differenz, repro_pfad: v.repro_pfad, schwere: v.schwere, unabhaengig: v.verdict.unabhaengig })) }