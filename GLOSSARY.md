# Glossary

**Log entry**: one dated record of what changed in a bundle and why, kept in a file of its own so that no two changes write the same file.
_Avoid_: log line, changelog fragment

**Frozen log**: the bundle's root `log.md` once log entries live on their own: it keeps the history written before the split and points to where entries go now; no change writes to it again.
_Avoid_: legacy log, log view

**Change hint**: the count of commits that touched a concept's governed paths since the concept's last commit, shown next to it in recall. It tells the reader where to look in the code; it obliges nobody to do anything.
_Avoid_: stale, drift, alarm

**Read-repair**: correcting a concept at the moment an agent, while relying on it, finds that the code says otherwise. The code wins; the concept is fixed as an ordinary edit.
_Avoid_: re-stamp, verification

**okf binary**: the `okf` command-line tool from okf-agent-memory that validates and searches a bundle; the gate accepts only the releases of it that were measured.
_Avoid_: okf version (unqualified), okf

**Format version**: the OKF specification release a bundle declares with `okf_version` in its root `index.md`; it says how the bundle's files are read, whatever tool reads them.
_Avoid_: okf version (unqualified), spec version

**Plugin pin**: the okf-drift release a consumer repository records in `.okf-drift-version`, which fixes the gate and recall scripts it runs.
_Avoid_: okf version (unqualified), pinned okf
