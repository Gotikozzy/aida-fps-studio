# Architecture

Read ../../SPECIFICATION.md for normative scope. `src/dg_fps` is the application;
`native` contains only its optional NVIDIA optical-flow bridge and MIT helper files.
Python package name `dg_fps` is retained for project compatibility; product name is AIDA.

Qt Widgets display state and collect user intent. Asynchronous jobs/controllers manage
opening and analysis; media modules decode/index frames; cadence and evidence modules
produce structured measurements; presentation/export modules render deliveries. UI text
must not become an analyzer input. Heavy work stays off the UI thread. GPU access is
serialized; optional hardware is not a startup dependency.

Progressive opening has two products: navigation preview (first frame/thumbnails) and an
authoritative frame/PTS index. They have different purposes. Analysis/export wait for the
precise index. Index cache identity, parameters and source provenance must stay coherent.

0.8.15 preserves imported measurement sources with a SHA-256 manifest and changes legal
presentation, version and packaging. The optional update-check marker is UI/network policy.
It does not modify decoding, analysis or encoding. See ADR 0001 and verify_source_integrity.py.
Historical implementation details remain in ../reference/v0.8.14-ARCHITECTURE.md.

[Other language / Outro idioma](../pt-BR/ARCHITECTURE.md)
