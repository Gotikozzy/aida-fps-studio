# GitHub build validation / Validação do build GitHub

Date / Data: 2026-11-15. Product / Produto: AIDA FPS Studio 0.8.15.
Status: **unsigned candidate built successfully / candidato sem assinatura aprovado tecnicamente**.
This is not Foundation acceptance or a completed signed-release pilot.
Não representa aprovação da Foundation nem piloto de release assinada concluído.

## Traceability / Rastreabilidade

- [Build run / execução](https://github.com/Gotikozzy/aida-fps-studio/actions/runs/43756438064)
- [Reviewed PR / PR integrado](https://github.com/Gotikozzy/aida-fps-studio/pull/7)
- Build source commit: `7c2ae28552f994c9675669db2fa63f6d2694fc1b`.
- Protected-main merge commit: `66b4fb2d143d145edad75a34fcdfa1680998bebd`.
- Both commits have the same file tree: `554841f50d9834f20789653320572a246c4d1f49`.
- Windows-2022 GitHub-hosted runner; reference Python 3.12.7 and hash-pinned inputs.
- FFmpeg and the NVIDIA bridge compiled from source; no developer-local DLLs supplied.

Os commits de build e merge possuem a mesma árvore de arquivos. Compilação realizada
em runner GitHub hospedado, com entradas verificadas e sem DLLs da máquina do desenvolvedor.
Later documentation-only commits do not change the provenance of this candidate.
Commits posteriores de documentação não mudam a origem deste candidato.

## Checks / Verificações

- 411 tests passed with the rebuilt media runtime; zero failures/errors/skips.
- All 71 protected Python/C++/header files retain their 0.8.14 source hashes.
- Technical native inventory: 138 reviewed files; complete upstream notices and corresponding sources staged.
- NSIS installer completed. Frozen CPU self-test passed: 16 frames, 15 FPS content cadence,
  H.264 CPU / BT.709 export, PT/EN interface evidence.
- Local extracted executable self-test also passed; RTX 2080 SUPER/NVIDIA optical flow detected.
- Six deterministic, sequential GPU comparisons against the original 0.8.14 DLL produced
  exactly equal vectors and magnitudes (maximum vector difference 0.0). Both used one
  session, nine uploads and seven executions including the backend verification call.

411 testes passaram com runtime reconstruído, fontes protegidos preservados e revisão
nativa concluída. Autotestes do executável passaram no runner e localmente. Seis casos
GPU sintéticos foram idênticos à referência. Isso não substitui validação ampla com
vídeos reais nem constitui benchmark de desempenho.

## Final artifacts / Artefatos finais

| File / Arquivo | Bytes | SHA-256 |
|---|---:|---|
| AIDA-FPS-Studio-0.8.15-windows-x64-setup.exe | 229445299 | `330f08d0daf617804ea145d0d0594a19d19b16868f6dd6bc54c826d9319585b0` |
| AIDA-FPS-Studio-0.8.15-windows-x64-setup.zip | 229445485 | `f5c5277661f6387ec9ceefdb2bb71d24a5888a446f338cd334afc37b4a19fdda` |

GitHub artifact ID: `14178822854`, outer archive SHA-256:
`c07d55d349f65705db8576368e2546221affd532394b89512168e087d458df67`.
Downloaded files match GitHub's digest and the embedded final checksums. Installer
FileVersion is 0.8.15; Authenticode status is **NotSigned**. SignPath remains disabled.
Hashes conferidos; versão 0.8.15; assinatura ausente conforme esperado nesta etapa.

## Additional regression / Regressão adicional

Four private real-video windows of 120 frames each (480 total) matched between
0.8.14 and 0.8.15: decoded pixels, PTS/time base, signals and CPU/NVIDIA analysis
results. Only generated finding UUIDs and the native-library filesystem path were
excluded from analysis comparison. GPU calls ran sequentially on RTX 2080 SUPER.
The candidate used the GitHub-built native media/bridge with pinned PyAV Python
wrappers in an isolated Python environment. This was not a full frozen-EXE video
comparison, a whole-dataset validation or a performance benchmark. Private footage
and paths are not published. [Sanitized summary](validation/real-video-comparison.json).

Quatro trechos reais de 120 quadros produziram os mesmos pixels, PTS/time base,
sinais e resultados CPU/NVIDIA. Apenas UUIDs gerados e caminho da biblioteca foram
excluídos da comparação. O teste usa runtime nativo do GitHub em Python isolado;
não é comparação integral de vídeos pelo EXE congelado nem benchmark.

The [original-installer pilot](INSTALLER_PILOT.md) passed all 13 checks for each
legacy version (0.8.12 and 0.8.14), including frozen CPU analysis/export, normal
project opening, reinstall, downgrade/lock refusal and safe uninstall.
CI for the added pilot checks passed **419 tests**; the original native-build run
above retains its own 411-test count.

O piloto dos instaladores originais passou nas duas versões. A CI com os controles
adicionais passou em 419 testes; o build nativo original permanece documentado com 411.

## Limits and next gates / Limites e próximas etapas

The hosted runner has no NVIDIA driver; numerical GPU comparisons were local.
The real-video comparison covers sampled windows only. The installer pilot used
disposable GitHub VMs and did not touch the user's working installation. The [candidate SBOM](RELEASE_SBOM.md) is recorded. Foundation onboarding, system-library acceptance and
inner-file/uninstaller signing remain required.

O runner não tem driver NVIDIA. Os testes locais de GPU e os trechos reais têm
escopo delimitado. A instalação foi testada em VMs descartáveis. O SBOM do candidato está registrado; onboarding, aceite das bibliotecas de sistema e assinatura continuam pendentes.
No site update manifest was published. Nenhum manifesto de atualização foi publicado.
