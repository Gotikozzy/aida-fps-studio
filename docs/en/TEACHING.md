# Software engineering teaching guide

Use a fixed tag and a separate student branch. Keep the production baseline available.

| Topic | Exercise | Evidence required |
|---|---|---|
| Requirements | Separate capture FPS from content cadence | Scope and acceptance examples |
| Architecture | Trace UI -> job -> decoder -> evidence | Component diagram and ADR |
| Testing | Add a timestamp edge-case fixture | Failing example then regression result |
| Performance | Compare cold/warm opening | Hardware, cache, repetitions, identical outputs |
| Supply chain | Trace one DLL to source/license | Version, hash, notice, corresponding source |
| Release engineering | Build a candidate from a clean checkout | Commit, logs and final hashes |
| Security | Model update-origin compromise | Trust boundaries and mitigations |

Students must label measured and inferred claims and provide visual evidence. Do not use
private gameplay as a required exercise input. Synthetic fixtures in tests/conftest.py are
small and reproducible. A passing test suite does not prove every gameplay conclusion.
Review contributions normally; a course exercise must not silently change production
thresholds, licensing or signing workflows. Grade traceability and limits, not just speed.

[Other language / Outro idioma](../pt-BR/TEACHING.md)
