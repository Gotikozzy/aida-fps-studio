# AIDA FPS Studio 0.8.11 — restauração responsiva dos painéis

Correção exclusiva da interface. A abertura continua centralizada e utiliza
o tamanho padrão da janela. As divisões internas são aplicadas depois que a
área de análise estiver visível e dimensionada, incluindo a troca a partir
da guia Início.

As preferências guardam proporções horizontais e verticais. Larguras antigas
em `panel_sizes` são migradas sem apagar os demais ajustes. A adaptação a uma
tela menor não substitui as proporções escolhidas; alterações manuais nos
divisores passam a ser a preferência. Projeto e Resultados têm larguras mínimas
úteis e os painéis não podem ser recolhidos por completo. Restaurar painéis
recupera as duas divisões com padrão adaptado ao espaço disponível.

Sem alteração dos algoritmos, parâmetros, medições, relatórios ou apresentação
dos vídeos. Versões dos analisadores e dependências preservadas.

## Validação

- 367 testes aprovados; Ruff aprovado nos arquivos alterados.
- 11 testes de layout: preferências inválidas, migração do caso 215/1303/54,
  preservação das proporções ao reduzir/ampliar, movimentação dos divisores,
  divisão vertical, abertura pela guia Início e restauração completa.
- Conferência visual em janela nativa de 1300 × 850 com preferências antigas:
  Projeto 240 px, monitor 747 px e Resultados 285 px.
- Executável congelado: self-test aprovado, análise, exportação H.264 CPU,
  relatórios e interface PT/EN.
- Instalador com carga real em identidade isolada: instalação nova, atualização,
  reinstalação, conferência dos arquivos instalados, bloqueio de arquivos em uso
  e downgrade, atalhos, associação de extensão isolada, preservação de projeto
  e desinstalação. Instalação e preferências reais do usuário preservadas.
- Revisão automatizada dos componentes nativos autoriza o pacote público;
  licenças e termos existentes incluídos.

Evidências em `build/tests-0811.log`, `build/layout-0811-visual/geometry.json`,
`build/self-test-0811/self-test.json` e `build/full-installer-0811.log`.

Publicação remota pelo responsável pelo site. Enviar ZIP e SHA-256 antes
de ativar o manifesto local atualizado. Sem mudança de Nginx para esta versão.

Pacote: `AIDA-FPS-Studio-0.8.11-windows-x64-setup.zip`.
Tamanho: 230524854 bytes.
SHA-256: `fc3c07d0976dbb41de7f2ceb1e9adf03b2d92dcb8d9054372dc53f18223cd5b3`.
Preparado em `E:/dg_apps/site_course/static/aida/` com o manifesto 0.8.11.
