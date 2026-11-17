# Procedimento de release Windows

A release é distribuída sem assinatura Authenticode do projeto. Os requisitos de
build e publicação estão abaixo e na [política de distribuição](../../CODE_SIGNING.md).

1. Revise origem de dependências e imagens, licenças, segurança e documentação bilíngue.
   Confira a versão em `pyproject.toml`, `src/dg_fps/__init__.py` e na tag pretendida.
2. Faça commit das alterações revisadas. O pacote de fontes arquiva Git `HEAD`, não
   arquivos pendentes. Execute as [verificações de fontes](../../.github/workflows/ci.yml)
   e o [build manual Windows](../../.github/workflows/windows-candidate.yml) nesse commit.
3. Confira testes, integridade da medição, runtime de mídia reconstruído, inventário
   nativo, fontes correspondentes, avisos e autoteste CPU do executável. Registre URL
   da execução, commit, ferramentas e logs. Valide GPU separadamente em hardware compatível.
4. Verifique instalação, abertura por CPU, projetos, análise, exportação, reinstalação,
   atualizações de versões anteriores suportadas e desinstalação. Use o
   [piloto isolado](../INSTALLER_PILOT.md) para testes que modificam o sistema.
5. Confirme que o estado de assinatura do instalador/aplicativo corresponde à política
   sem assinatura. Preserve assinaturas de terceiros. Adesão a serviços e certificados
   não são critérios de liberação.
6. Execute `python scripts/finalize_artifacts.py` com o instalador final. Confira hashes
   do EXE e ZIP, conteúdo do arquivo, versão e tamanho/hash de `update.candidate.json`.
   As saídas ficam em `dist/installer/public/`; o pacote de fontes fica em `dist/`.
7. Gere ou revise o inventário de dependências/SBOM para o instalador exato. O
   [SBOM registrado](../RELEASE_SBOM.md) e seu gerador estão fixados ao hash de um
   candidato histórico; reconstruções exigem inventário verificado e revisão do gerador.
8. Aprove os artefatos para publicação. Publique arquivos versionados imutáveis e
   checksums na release do repositório. Espelhe os mesmos bytes do instalador/ZIP no site.
   Confira disponibilidade e hashes; publique `update.json` por último. Consulte as
   [restrições de hospedagem e atualização](UPDATES.md).

Não substitua o instalador de uma versão publicada. Reconstruir os mesmos fontes pode
mudar os bytes; registre novos hashes e evidências. O [registro do candidato anterior](../GITHUB_BUILD_VALIDATION.md)
não valida uma reconstrução posterior.

Proteja branches/tags, alterações de workflows e credenciais; use MFA nas contas
mantenedoras e revisão humana da release. PRs de forks não recebem credenciais de
publicação. O workflow de candidato envia artefatos para revisão, sem publicar release
ou alterar o site. Falha em verificação obrigatória interrompe a publicação.

[English](../en/RELEASE.md)
