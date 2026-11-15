# Local preparation validation / Validação local

Date / Data: 2026-11-15. Package / Pacote: AIDA FPS Studio 0.8.15.

- Fresh isolated CPython 3.12.7 environment: 27 reference wheels installed with SHA-256 enforcement.
- Dependency closure: pip check passed; editable application build/installation passed.
- Complete regression suite: **409 passed in 86.10 seconds** (CPU/development wheel runtime).
- Source integrity: **71 imported Python/C++/header files unchanged** against 0.8.14.
- Application differences limited to version, two legal UI text files and offline update-check switch.
- Five added tests cover baseline, licensing metadata, offline mode and build-input confinement/integrity.
- Ruff checks for new/modified packaging tools: passed. PowerShell candidate script parsed successfully.
- Python source distribution built successfully. Local Markdown links checked with no missing targets.
- All 12 pinned upstream input URLs responded HTTP 200 to availability checks.
- NVIDIA bridge compiled from unchanged C++ sources with verified CUDA driver headers/import library; product metadata reports 0.8.15.
- Source self-test: passed (16 synthetic frames, H.264 CPU/BT.709 export, content cadence 15 FPS); rebuilt bridge/driver/NVENC detected on RTX 2080 SUPER. This is not a numerical GPU equivalence test.
- Source package contains only dg_fps; no imports from other DG analyzer modules.

Ambiente CPython novo com 27 wheels verificados; dependências, instalação e build de
fontes aprovados. Suíte completa com 409 testes; 71 fontes preservados. Mudanças do
aplicativo limitadas à versão, textos legais e marcador offline. Novos testes cobrem
privacidade, metadados, integridade e confinamento. Links e URLs de entrada verificados.

Limits / Limites: these are local results, not a clean GitHub Actions build or a signed
production pilot. The test run uses the reference development PyAV wheel runtime, not
a fresh rebuild of FFmpeg. GPU numerical equivalence was not re-measured in this run.
Foundation approval, actual repository/account configuration, asset rights and installed
signature validation remain release gates in SIGNPATH_READINESS.md.

Resultados locais não são build GitHub nem piloto assinado. Testes usam wheel PyAV de
desenvolvimento; não reconstroem FFmpeg. Equivalência numérica GPU não foi reavaliada.
Aprovação, contas, direitos das imagens e assinaturas instaladas seguem no checklist.
