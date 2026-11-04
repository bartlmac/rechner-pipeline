# Sicherheit

## Eine Sicherheitslücke melden

Bitte nicht als öffentliches Issue, Pull Request oder Kommentar. Gemeldet
wird privat über GitHub: im Reiter **Security** des Repositorys mit
**Report a vulnerability**, direkt unter
<https://github.com/bartlmac/rechner-pipeline/security/advisories/new>.
Die Meldung sehen nur die Maintainer.

In die Meldung gehören der betroffene Stand (Commit oder Zweig), die
Schritte, mit denen sich die Lücke zeigen lässt, und ihre Wirkung. Keine
Zugangsdaten und keine echten Daten in der Meldung.

## Wie es weitergeht

Das Maintainer Office bestätigt den Eingang und bewertet die Meldung. Die
Arbeit an der Behebung läuft in einem privaten Security Advisory des
Repositorys; dort laufen auch Befunde aus eigenen Prüfungen. Veröffentlicht
wird ein Advisory erst, wenn die Behebung in `main` ist.

## Geltungsbereich

Das Repository ist ein Prototyp, kein Produkt (siehe `README.md`). Es gibt
keine gepflegten Releases; Behebungen gehen nach `main`.
