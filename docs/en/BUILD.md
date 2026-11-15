# Windows build from source

## Prerequisites

Windows x64, Python **3.12.7** for the reference composition, Git, Visual Studio 2022 C++
Build Tools (MSVC/x64/Windows SDK), CMake and 7-Zip available on PATH. Developer media
inputs are fetched from pinned HTTPS locations and checked with SHA-256. NVIDIA's driver
headers/import library are build-only inputs; users need a driver, not CUDA Toolkit.
Review the CUDA download's own terms. No proprietary SDK runtime is added by this step.

```powershell
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install --require-hashes -r requirements-windows.lock
.venv/Scripts/python -m pip install --no-deps --no-build-isolation -e .
./scripts/build_candidate.ps1 -Python .venv/Scripts/python.exe
```

The candidate script checks the source baseline, fetches media/Qt/CUDA/NSIS inputs,
extracts the verified toolchain, builds FFmpeg, rebinds PyAV import names, builds the NVIDIA
bridge, runs tests with that media runtime, freezes the app, stages notices/sources,
classifies native dependencies and creates an **unsigned** installer and checksums.
Run from a committed checkout: package_release.py archives Git HEAD. A clean candidate
build has not been demonstrated merely by shipping this script; record the actual run.

FFmpeg 8.0.1, PyAV 16.1.0, OpenH264 2.6.0 and dav1d 1.5.1 retain the reference composition;
GPL/nonfree codec enablement stays off. Do not replace it with the stock PyAV wheel's
vendored FFmpeg for a production build. Do not use --legacy-media-qa for release.
Versioned manifests: build-support/*.json. Native tool prerequisites are distinct from
runtime requirements. Bootstrap does not execute downloaded self-extracting EXEs.

Full sources are staged under installer/corresponding-sources and included by the installer.
Upstream archive availability and rights must be checked during release review. Unknown
native components fail the distribution gate; classification is not legal approval.
The native-review script's component allowlist must be reviewed, not blindly expanded.

Outputs: dist/<version>/AIDA-FPS-Studio and dist/installer/public. The latter contains a
retained EXE, ZIP, hashes and update.candidate.json. No script uploads the site manifest.
Sign before final hashes. These builds aim for traceable inputs, not a promise of identical
binary hashes across compilers, timestamps or signatures. GitHub CI must be run separately.

[Other language / Outro idioma](../pt-BR/BUILD.md)

CI runs candidate stages separately for visible progress and failure isolation. Locally,
`./scripts/build_candidate.ps1 -Stage <stage>` runs one stage; the default runs all stages.
The frozen self-test is awaited and its JSON status must pass before final packaging.
