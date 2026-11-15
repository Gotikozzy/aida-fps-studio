# AIDA FPS Studio development instructions

This repository contains only AIDA FPS Studio. Read SPECIFICATION.md first.
Use Python 3.12, PySide6/Qt Widgets and pathlib.Path. Keep analysis outside UI.
Preserve PTS, time base, frame provenance, analyzer versions, parameters and ROI.
Distinguish measured, inferred, heuristic and manual conclusions.
Serialize GPU work; NVIDIA acceleration is optional at runtime.
No web UI, HTTP service, LLM or additional analyzer modules are in scope.
Record architecture changes in docs/adr/ before implementing them.
Use structured logging, UTF-8, typed code and subprocess argument lists.
Critical changes require meaningful tests. Measurement changes require visual
evidence and an explicit versioned methodology decision. Keep PT/EN docs aligned.
Never sign third-party binaries with the project's signing policy.
First measure, then prove visually, then explain.
