"""Quellsystem-Tooling: die Bestandsfuehrung der abgebenden Gesellschaft.

Simulations-Tooling, KEIN Teil des Systems (Beschluss 2026-08-31: ADRs
gelten dem System; dieses Paket gehoert wie die Bestands-Simulation zum
Gesamtbild, README-Komponente (5)). Harte Regel dieses Pakets:

    KEIN Import aus ``rechner_pipeline``.

Der Quellcode des Quellsystems ist fuer das Migrationsprojekt
unerreichbar; die Unabhaengigkeit der beiden Rechenwege — Kommutation
hier, Thiele im Ziel — ist der Wert der ganzen Vorfuehrung. Ein Test
haelt die Regel maschinell.
"""
