"""Tarif-Spezifikationen (Stage 2): SDD in gebundener Form.

Die Spez (:mod:`.schema`) parametriert das Kern-Rueckgrat und wird aus
der A-Box projiziert (:mod:`.erzeugen`) — inklusive des BERECHNETEN
Struktur-Urteils "Parametrierung oder neues Produkt". Sie ist gegen
die A-Box deterministisch validierbar (:mod:`.validierung`): die Spez
ist Projektion, nicht zweite Quelle. Generatoren erzeugen daraus die
menschenlesbare Fachspezifikation (P7) und die Kern-Parametrierung.
"""

from rechner_pipeline.spez.schema import (  # noqa: F401
    BACKBONE,
    Erweiterungsstelle,
    SPEZ_VERSION,
    StrukturUrteil,
    TafelAbleitung,
    TarifSpez,
    ZellSpez,
)
