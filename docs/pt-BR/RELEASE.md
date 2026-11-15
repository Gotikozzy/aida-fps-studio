# Procedimento de release

1. Revise licenças/imagens, dependências, segurança e documentação nos dois idiomas.
2. Integre código revisado e crie tag protegida compatível com pyproject e __version__.
3. Execute ci.yml e windows-candidate manual a partir do commit em runners GitHub hospedados.
4. Inspecione logs, integridade, composição nativa, fontes e teste do executável.
5. Conclua onboarding e piloto SignPath descritos em ../../CODE_SIGNING.md.
6. Assine arquivos próprios internos, empacote/assine desinstalador NSIS e depois instalador.
   O workflow sign-installer cobre só a última etapa e não publica.
7. Verifique cadeias Authenticode, timestamps, política do publicador e arquivos instalados.
8. Teste CPU, GPU opcional, upgrade 0.8.14, projetos, exportação e desinstalação.
9. Execute finalize_artifacts.py nos bytes finais. Gere inventário/SBOM revisado e registre
   commit, execução CI, ferramentas, solicitação de assinatura e hashes finais.
10. Publique assets imutáveis, espelhe os mesmos bytes no site e publique update.json por
    último. Não substitua instalador de uma versão publicada.

Proteja branches/tags e ambientes. MFA e aprovação humana são políticas obrigatórias.
Actions fixadas por SHA revisado; PRs de forks sem segredos. Falha bloqueia publicação.
Hash de candidato não é hash de arquivo assinado posteriormente.

Release e candidatura são passos externos manuais; nenhuma conta, URL ou aprovação foi
inventada. Complete ../SIGNPATH_READINESS.md antes.

[Other language / Outro idioma](../en/RELEASE.md)
