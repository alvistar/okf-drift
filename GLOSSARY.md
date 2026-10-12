# Glossary

**Log entry**: one dated record of what changed in a bundle and why, kept in a file of its own so that no two changes write the same file.
_Avoid_: log line, changelog fragment

**Frozen log**: the bundle's root `log.md` once log entries live on their own: it keeps the history written before the split and points to where entries go now; no change writes to it again.
_Avoid_: legacy log, log view
