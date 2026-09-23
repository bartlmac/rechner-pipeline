"""Der Testschluessel der Freigabesignatur — eine Naht, kein Geheimnis.

Seit die Zeichnungsschicht im Betriebseingang zu Ende gebaut ist (T26-03,
2026-09-22), prueft ``eingang_anlegen`` die Freigabesignatur eines A-M4-
Snapshots. Die Test-Snapshots (``test_betrieb_uebernahme.am4_snapshot``)
signieren mit diesem Schluessel, und ``conftest`` reicht den Ring an den
Betriebseingang — deterministisch, ohne dass eine der vielen
Registrierungsstellen in den Tests einen Ring tragen muss.
"""

from __future__ import annotations

import hashlib

TESTKEY: bytes = hashlib.sha256(b"rechner-pipeline: testschluessel der freigabe").digest()
TESTRING: dict = {hashlib.sha256(TESTKEY).hexdigest(): TESTKEY}
FREMDER_SCHLUESSEL: bytes = hashlib.sha256(b"ein anderer schluessel").digest()
