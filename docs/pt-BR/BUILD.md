# Build Windows a partir dos fontes

## Pré-requisitos

Windows x64, Python **3.12.7** na composição de referência, Git, Visual Studio 2022 C++
Build Tools (MSVC/x64/Windows SDK), CMake e 7-Zip no PATH. Entradas de mídia vêm de
HTTPS com SHA-256 fixado. Headers/import library NVIDIA são ferramentas de build;
o usuário final precisa de driver, não CUDA Toolkit. Revise os termos do download CUDA.
Essa etapa não adiciona runtime proprietário do SDK.

```powershell
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install --require-hashes -r requirements-windows.lock
.venv/Scripts/python -m pip install --no-deps --no-build-isolation -e .
./scripts/build_candidate.ps1 -Python .venv/Scripts/python.exe
```

O script verifica baseline, baixa entradas mídia/Qt/CUDA/NSIS, extrai toolchain verificado,
compila FFmpeg, ajusta nomes de importação PyAV, compila ponte NVIDIA, testa com esse
runtime, congela aplicativo, reúne avisos/fontes, classifica dependências e gera instalador
**sem assinatura**. Use checkout commitado: package_release.py arquiva Git HEAD.
Fornecer o script não comprova execução limpa; registre a execução real.

FFmpeg 8.0.1, PyAV 16.1.0, OpenH264 2.6.0 e dav1d 1.5.1 mantêm a composição de
referência, sem habilitar GPL/nonfree. Não substitua pelo FFmpeg do wheel PyAV comum
em produção. --legacy-media-qa não é opção de release. Manifestos: build-support/*.json.
Ferramentas de build diferem dos requisitos de execução. Bootstrap não executa EXEs
autoextraíveis baixados; extrai-os como dados.

Fontes completos ficam em installer/corresponding-sources e acompanham instalador.
Disponibilidade e direitos exigem revisão na release. Nativos desconhecidos bloqueiam
a distribuição; classificação não é parecer jurídico. Revise a allowlist, não a amplie cegamente.

Saídas: dist/<versão>/AIDA-FPS-Studio e dist/installer/public. Esta mantém EXE, ZIP,
hashes e update.candidate.json. Nenhum script publica manifesto no site. Assine antes
dos hashes finais. Objetivo é rastreabilidade, sem prometer hashes binários idênticos
entre compiladores, timestamps ou assinaturas. Execute CI GitHub separadamente.

[Other language / Outro idioma](../en/BUILD.md)
