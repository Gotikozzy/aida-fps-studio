# AIDA FPS Studio 0.8.15

[![Source checks](https://github.com/Gotikozzy/aida-fps-studio/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Gotikozzy/aida-fps-studio/actions/workflows/ci.yml)
[English](README.md) · [Manual](docs/pt-BR/USER_GUIDE.md) · [Build](docs/pt-BR/BUILD.md) · [Contribuição](CONTRIBUTING.md)

Aplicativo nativo Windows para examinar **cadência visual observável e FPS**, organizar
projetos locais `.aida` e exportar evidências. Python 3.12, PySide6/Qt Widgets, PyAV e
fluxo óptico NVIDIA opcional. Este repositório contém somente o AIDA FPS Studio.

![AIDA FPS Studio](src/dg_fps/assets/studio-example.png)

## O que é medido

FPS da captura difere da cadência observável do conteúdo. Compressão, perdas de captura,
interpolação, quadros repetidos e transições limitam conclusões. O AIDA não mede diretamente
o renderizador interno de um jogo. Resultados preservam timestamps, proveniência,
parâmetros e versões. Consulte a [metodologia](docs/pt-BR/METHODOLOGY.md).

## Instalação e primeira análise

Windows 10/11 x64. Funciona em CPU; NVIDIA exige GPU compatível e driver instalado,
sem CUDA Toolkit no computador do usuário. Use instaladores publicados na página
verificada do projeto. Abra um vídeo, aguarde o índice preciso, selecione trecho/ROI,
analise e inspecione as evidências antes de exportar. Miniaturas progressivas servem
à navegação enquanto o índice autoritativo é preparado.

**Situação:** 0.8.15 preparada como release aberta. Este pacote de fontes não comprova
um instalador público assinado nem aprovação pela SignPath. Repositório oficial: https://github.com/Gotikozzy/aida-fps-studio.
Não se declara aprovação ou assinatura pela SignPath.
Site oficial existente: https://detonandogueek.com.br/aida.

## Desenvolvimento

```powershell
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install --require-hashes -r requirements-windows.lock
.venv/Scripts/python -m pip install --no-deps --no-build-isolation -e .
.venv/Scripts/python scripts/check_repository.py
.venv/Scripts/python scripts/verify_source_integrity.py
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m dg_fps
```

Wheels de desenvolvimento não são o runtime de mídia da release. Siga o
[guia de build](docs/pt-BR/BUILD.md) para reconstruir a composição FFmpeg validada.

## Documentação

- [Arquitetura](docs/pt-BR/ARCHITECTURE.md) e [escopo normativo](SPECIFICATION.md)
- [Validação](docs/pt-BR/VALIDATION.md), [release](docs/pt-BR/RELEASE.md), [atualizações](docs/pt-BR/UPDATES.md)
- [Privacidade](PRIVACY.md), [segurança](SECURITY.md), [guia para o curso](docs/pt-BR/TEACHING.md)
- [Changelog](CHANGELOG.md) e [decisões](docs/adr/0001-standalone-open-source-release.md)

## Code signing policy

[Política de assinatura](CODE_SIGNING.md). A assinatura **não está configurada nem aprovada**
neste pacote local. Uma release de produção exige origem CI verificável e aprovação manual.

## Licença

Código próprio: [Apache-2.0](LICENSE). Terceiros mantêm suas licenças:
[avisos](THIRD_PARTY_NOTICES.md), [escopo](docs/pt-BR/LICENSING.md), [imagens](docs/ASSETS.md).
Vídeos e projetos continuam sendo do usuário. Documentos históricos 0.8.14 não regem a
licença da 0.8.15. Outros módulos do DG Graphics Analyzer não estão incluídos.

[GitHub build validation / Validação do build GitHub](docs/GITHUB_BUILD_VALIDATION.md)
