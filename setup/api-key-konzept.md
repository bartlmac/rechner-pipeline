# API-Key-Schutz für `rechner-pipeline` im KI-Lab

Stand: 2026-04-28

## Entscheidung

Use Case (3) „agentisch" läuft am Stand **ausschließlich auf den Laptops von Bartek und Arno**. Die drei Helfer-Demo-Laptops bekommen **keinen** API-Key — `pipeline.py`/`agentic_pipeline.py` schlagen dort mit `RuntimeError: OPENAI_API_KEY is not set` fehl, was gewollt ist. Helfer zeigen Use Cases (1), (2), (4).

Damit reicht ein **schlanker Schutz**:

1. Klartext-`.env` mit dem `OPENAI_API_KEY` nur auf Bartek- und Arno-Laptop.
2. NTFS-ACL auf `.env`, sodass nur der eigene User lesen darf — verhindert versehentlichen Zugriff durch andere lokale User (z. B. Admin-Account, Helfer-User).
3. **OpenAI-Dashboard Hard Limit auf 50 EUR** als zweite Schutzebene unabhängig vom lokalen Schutz.

Keine Verschlüsselung, keine Passphrase, kein Wrapper — der Workflow bleibt das `pipeline.py`/`agentic_pipeline.py`-Direkt-Aufrufmuster aus dem README.

## Operativer Ablauf

**Bartek- und Arno-Laptop** (jeweils einmalig nach `setupdav.ps1`):

```powershell
cd "$env:USERPROFILE\ki-lab\repos\rechner-pipeline"

# 1. .env mit Klartext-Key anlegen (oder bestehende vom Skript behalten):
notepad .env
#   Inhalt: OPENAI_API_KEY=sk-...
#   speichern, schließen

# 2. ACL setzen — nur der aktuelle User darf lesen:
.\setup\set-env-acl.ps1
```

**Helfer-Laptops**: nichts tun — `.env` bleibt mit leerem `OPENAI_API_KEY` (aus `.env.example`).

**OpenAI-Dashboard** (einmalig, vor JTG):

- Settings → Limits → Hard limit `50` USD/EUR
- Optional: Soft limit `30` + E-Mail-Alert

## Restrisiken

- **Lokaler Admin** auf der Maschine könnte den ACL-Schutz umgehen (Owner ändern). Mitigation: nur die zwei vertrauenswürdigen Laptops (Bartek/Arno) bekommen den Key überhaupt.
- **Bartek-Laptop verloren/gestohlen** während JTG: Key ist im Klartext lesbar. Mitigation: 50-EUR-Cap, Key nach JTG sofort rotieren.
- **Helfer mit physischem Zugriff** auf Bartek-Laptop in einem unbeaufsichtigten Moment: kann `.env` lesen. Mitigation: Standpräsenz; in Pausen Laptop sperren (`Win+L`).

Diese Risiken sind akzeptabel für die Veranstaltung.

---

## Anhang — verworfene Optionen (für die Akte)

| Option | Warum nicht jetzt |
|---|---|
| Windows DPAPI (User-bound) | Schützt nur zwischen Windows-Usern. Auf Demo-Maschinen mit Shared-Account nutzlos. |
| Passphrase + AES-GCM (`.env.encrypted`) | Robust, aber unnötig für unser Setup, weil Helfer-Laptops gar keinen Key sehen. Bartek bräuchte sonst einen Wrapper-Aufruf bei jedem Lauf. |
| Hybrid (DPAPI + Passphrase) | Overkill. |

Wenn sich das Setup-Modell später ändert (z. B. Helfer sollen (3) auch starten können), ist die Passphrase-Variante der saubere Upgrade-Pfad.
