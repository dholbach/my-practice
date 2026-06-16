# P-021: Git-History-Bereinigung

**Status**: DONE (März 2026)

## Ziel

Bereinigung der Git-History: Entfernen von ggf. versehentlich eingecheckten
sensiblen Daten (echte Namen, Kontaktinfos) aus älteren Commits.

## Durchgeführt
- `git filter-repo` oder `BFG Repo Cleaner` zur History-Rewrite
- Repo neu auf GitHub gepusht (Force-Push nach Bereinigung)
- Alle lokalen Clones danach auf den neuen Stand gebracht

## Ergebnis
- Saubere Git-History ohne PII in alten Commits
- Remote-History überschrieben
