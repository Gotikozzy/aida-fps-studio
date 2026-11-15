# Validation and evidence

Run source integrity and repository checks, then `python -m pytest -q`. Tests use small,
seeded synthetic FFV1 fixtures rather than redistributing private gameplay. The import
baseline covers application sources except explicit version/legal/offline UI changes,
and native C++/headers. It protects this packaging release; later deliberate algorithm
changes require a new reviewed baseline, not automatic hash refresh.

Test layers: unit/media/cadence, controllers/UI, update ZIP confinement and size/hash checks,
installer path handling and third-party source/notice requirements. Run the frozen EXE
with `--self-test <empty-output-directory>` after building. CPU checks are mandatory;
GPU comparison requires compatible hardware and must record driver/backend versions.
A hosted CPU test is not GPU validation. Check install/upgrade/uninstall on a test account.

Historical 0.8.14 evidence is retained under ../reference with its original limitations.
It is not a successful 0.8.15 clean build, signed release or independent scientific audit.
Local 0.8.15 preparation results are in ../LOCAL_VALIDATION.md.

Benchmark reports identify CPU/GPU, driver, OS, input properties, cache state, repeated
runs and variability. Distinguish first-frame latency, first-thumbnail latency and full
index completion. Compare measurement outputs/PTS/provenance, not timing alone.
Do not publish private source paths or clips; use distributable synthetic fixtures.

[Other language / Outro idioma](../pt-BR/VALIDATION.md)

[Verified GitHub candidate / Candidato verificado](../GITHUB_BUILD_VALIDATION.md).
