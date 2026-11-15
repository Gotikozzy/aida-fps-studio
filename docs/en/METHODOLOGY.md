# Measurement methodology

A captured video is the observable input, not direct engine telemetry. Capture rate,
decoder frame sequence and observable content cadence are different quantities. Repeated
images may reflect capture behavior, a held scene or rendering behavior; evidence and
uncertainty constrain attribution. Do not infer engine FPS from a label alone.

Preserve each frame's PTS/time base and source index. Retain source identity, ROI, analyzer
version, parameters and selected backend. Variable frame rate and ambiguous timestamps
must be handled explicitly. Use measured/inferred/heuristic/manual labels accurately.
Navigation thumbnails never substitute for measurement frames. Inconclusive results stay
inconclusive; presentation smoothing is not an additional observation.

For an investigation: define the question, record capture conditions, inspect source
quality, select range/ROI, measure, inspect visual evidence and only then explain. Export
structured results alongside contextual evidence. Reproduce with the same source and
parameters before comparing performance changes.

Open licensing and digital signatures do not certify the scientific validity of every
result. Changing thresholds, decode behavior or GPU algorithms requires new validation,
methodology/version review and an ADR; it is outside this packaging release.

[Other language / Outro idioma](../pt-BR/METHODOLOGY.md)
