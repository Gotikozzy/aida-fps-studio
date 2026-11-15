# AIDA FPS Studio 0.8.9 — movimento localizado com contexto temporal

Regra global para cenas com câmera estável: a validação espacial pode reunir
movimentos locais já confirmados pelo optical flow durante até 0,5 segundo da
fonte. Exige pelo menos três avanços, separados por um intervalo total mínimo
de 0,1 segundo, abrangendo as mesmas seis células, três colunas e duas linhas
exigidas anteriormente para movimento simultâneo. Não considera jogo, arquivo
ou meta de FPS para aceitar uma cena.

Movimento amplo anterior não entra nessa janela local. Cortes, perda de sinal,
PTS inválidos/não monotônicos, lacunas e mudanças de trecho reiniciam o contexto.
Uma confirmação pode recuperar as decisões brutas da janela; quadros realmente
repetidos permanecem repetidos. A confirmação precisa continuar sustentada por
evidência recente. Um pequeno overlay imóvel na mesma região permanece protegido.

Não foram alterados comparação de pixels, cálculo/validação do optical flow,
decodificação, temporização, metas ou composição do vídeo. A interpretação espacial
é heurística e agora registra a janela e o instante de confirmação nos dados.
Não existe identificação semântica garantida de HUD/personagem/efeito.

Versão do analisador: 0.8.0. Política espacial: 1.1.0.
**É necessário analisar novamente o vídeo para obter a nova classificação.**
Projetos salvos e relatórios existentes não são reescritos automaticamente.

Validações concluídas:

- 335 testes passaram; Ruff sem erros. Incluem capturas/cadências 30, 40, 60,
  120 e 59,94/29,97, repetições, overlay central/periférico, cortes, perda de
  continuidade, expiração da confirmação e preservação de PTS/evidência bruta.
- Replay de 34.129 quadros em cinco análises existentes: decisões antigas
  reproduzidas antes da comparação, evidências brutas e arquivos de entrada
  preservados. Gears: partial_hold de 772 para 128 quadros; GTA de 24 para 9 em
  uma análise. Outra análise de GTA, Starfield e UE5 mantiveram as decisões.
  Replay de escopo não equivale a nova decodificação nem a verdade de FPS.
- O único algoritmo existente alterado foi `_mark_scope_changes`; a função
  auxiliar `_distributed_scope` foi adicionada. Comparadores e temporização
  conferidos por comparação estrutural das funções.
- Instalador completo passou em instalação nova, upgrade, reinstalação,
  comparação de arquivos, bloqueio por aplicação em uso/downgrade, atalhos,
  preservação de projeto e desinstalação em identidade isolada.
- Setup público extraído: 553 arquivos conferidos por hash, 140 arquivos nativos
  aprovados pela revisão de distribuição e self-test aprovado.
- Nova decodificação/análise dos 4.849 quadros selecionados do Gears original:
  4.847 comparações NVIDIA, sem fallback CPU. Todos os dados básicos por par
  (pixels/métricas, movimento, repetições, índices, PTS e time bases) idênticos
  à análise anterior. A nova classificação reproduziu o replay (128 partial_hold).
  Prévia real de exportação conferida no ponto de cobertura do frame 27899.

Evidências: `build/tests-089-final.log`, `build/scope-089-replay.json`,
`build/full-installer-089.log`, `build/installer-089-public-proof/validation.json`.
Evidência da nova análise: `build/v089-real/fresh-validation.json`,
`build/v089-real/comparison.json` e `build/v089-real/preview-27899.png`.

Pacote: `AIDA-FPS-Studio-0.8.9-windows-x64-setup.zip`.
Tamanho: 230.514.401 bytes. SHA-256:
`ba81df7b9590571ea78b0124fd0930e10221815b9d306c0821698b2c85767c0c`.

ZIP e SHA preparados em `E:/dg_apps/site_course/static/aida/`; manifesto local
atualizado para 0.8.9 após validação. Publicação remota será feita pelo usuário.
