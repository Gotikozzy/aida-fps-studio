# AIDA FPS Studio 0.8.15

[![Source checks](https://github.com/Gotikozzy/aida-fps-studio/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Gotikozzy/aida-fps-studio/actions/workflows/ci.yml)
[Português](README.pt-BR.md) · [User guide](docs/en/USER_GUIDE.md) · [Build](docs/en/BUILD.md) · [Contributing](CONTRIBUTING.md)

Native Windows studio for examining **observable video cadence and FPS**, organizing
local `.aida` projects and exporting visual evidence. Python 3.12, PySide6/Qt Widgets,
PyAV and optional NVIDIA optical flow. This repository contains only AIDA FPS Studio.

![AIDA FPS Studio](src/dg_fps/assets/studio-example.png)

## What is measured

Capture FPS is distinct from observable content cadence. Compression, capture loss,
interpolation, repeated frames and scene transitions can limit conclusions. AIDA does
not directly measure a game's internal renderer. Results retain timestamps, provenance,
parameters and analyzer versions. [Methodology](docs/en/METHODOLOGY.md).

## Installation and first analysis

Windows 10/11 x64. CPU operation is supported; NVIDIA requires a compatible GPU and
installed display driver, not a CUDA Toolkit on the user's computer. Use a published
installer from the project's verified release page. Open a local video, let the precise
index complete, select a range/ROI, run analysis and inspect the evidence before export.
Progressive thumbnails are navigation aids while the authoritative index is prepared.

**Distribution status:** 0.8.15 is prepared as an open-source release. This source package
is not evidence of a signed public installer or SignPath Foundation acceptance.
Source repository: https://github.com/Gotikozzy/aida-fps-studio.
Official site: https://detonandogueek.com.br/aida.

## Development

```powershell
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install --require-hashes -r requirements-windows.lock
.venv/Scripts/python -m pip install --no-deps --no-build-isolation -e .
.venv/Scripts/python scripts/check_repository.py
.venv/Scripts/python scripts/verify_source_integrity.py
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m dg_fps
```

Development wheels are not the release media runtime. Follow [BUILD](docs/en/BUILD.md)
for the validated FFmpeg composition and clean Windows candidate build.

## Documentation

- [Architecture](docs/en/ARCHITECTURE.md) and [normative scope](SPECIFICATION.md)
- [Validation](docs/en/VALIDATION.md), [release process](docs/en/RELEASE.md), [updates](docs/en/UPDATES.md)
- [Privacy](PRIVACY.md), [security](SECURITY.md), [teaching guide](docs/en/TEACHING.md)
- [Changelog](CHANGELOG.md) and [architecture decisions](docs/adr/0001-standalone-open-source-release.md)

## Code signing policy

[Code signing policy](CODE_SIGNING.md). Signing is **not configured or approved** in this
local source package. Production release requires verified CI origin and manual approval.

## License

Owned application code: [Apache-2.0](LICENSE). Third-party licenses remain applicable:
[notices](THIRD_PARTY_NOTICES.md), [licensing scope](docs/en/LICENSING.md), [asset inventory](docs/ASSETS.md).
User videos and projects remain user content. Historical 0.8.14 documents are references,
not the licensing authority for 0.8.15. No additional DG analyzer modules are included.

[GitHub build validation / Validação do build GitHub](docs/GITHUB_BUILD_VALIDATION.md)
