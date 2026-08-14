"""Ontologie der Migrations-Pipeline: das einzige Stage-Interface.

T-Box (:mod:`.tbox`, Domaenenmodell) ist menschlich verantwortet und
versioniert; die A-Box (Instanzen eines Migrationsfalls) wird von
Agenten befuellt und liegt als deterministisches JSON im
Fall-Arbeitsbereich (:mod:`.abox`). Aussagen tragen Provenienz,
Zustand und Konfidenz (:mod:`.aussage`, P1/P3); Widersprueche zwischen
Quellen sind Modellobjekte (:mod:`.diskrepanz`, P2) und entstehen im
deterministischen Merge (:mod:`.merge`, P4); Coverage misst den
Pflichtumfang je Tarif (:mod:`.coverage`, P6).

Kein Agent einer spaeteren Stufe liest Rohquellen einer frueheren:
Stage 2 und 3 konsumieren ausschliesslich die A-Box.
"""

from rechner_pipeline.ontologie.aussage import (  # noqa: F401
    Aussage,
    Lesart,
    Provenienz,
    Zustand,
    belegt,
    nicht_belegt,
)
from rechner_pipeline.ontologie.diskrepanz import (  # noqa: F401
    Diskrepanz,
    Entscheidung,
    diskrepanz_id,
)
from rechner_pipeline.ontologie.tbox import (  # noqa: F401
    ABox,
    BEKANNTE_PARAMETER,
    Merkmalsdimension,
    OPTIONALE_PARAMETER,
    PFLICHT_PARAMETER,
    Parametrierungszelle,
    Quelle,
    TBOX_VERSION,
    Tarifgeneration,
)
