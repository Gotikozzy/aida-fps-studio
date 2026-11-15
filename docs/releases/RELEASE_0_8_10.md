# AIDA FPS Studio 0.8.10 — retenção qualificada e incerteza explícita

Rejeições espaciais provisórias não participam mais de períodos medidos sem
corroboração. Pares sem avanço validado, mas com pixels diferentes, precisam
de referências de movimento observável antes e depois dentro de 0,1 segundo
da fonte. As referências podem ser movimento validado distribuído ou refinamento
na resolução original com deslocamento >=0,5 pixel e confiança de suporte >=0,30.
Os critérios são globais; nomes de jogos, arquivos e metas não entram na decisão.

Estados novos: `scope_pending` e `motion_unresolved`. Ambos interrompem períodos
medidos e usam a projeção pontilhada já existente. O relatório mantém o FPS
medido nulo onde não há evidência suficiente; a referência continua separada.
Igualdade no vídeo original e igualdade apenas após redução de resolução são
identificadas separadamente. Repetições e métricas brutas continuam disponíveis.
Retenção por contexto permanece uma conclusão heurística, não telemetria do jogo.

Analisador 0.9.0, política espacial 1.2.0, política de retenção 1.0.0.
O JSON para LLM inclui a política e explica os novos estados. Não há suavização
adicional, comparação multiquadro que invente avanços intermediários, novo modelo,
dependência de GPU ou alteração do cálculo de optical flow.

**Reanalisar o vídeo para aplicar a nova classificação.** Projetos e relatórios
existentes não são reescritos automaticamente.

Validação:

- 356 testes passaram, Ruff sem erros. Incluem retenção comprimida em capturas
  60/120 e cadências 30/40/60, 59,94/29,97, origem da identidade de pixels,
  referências de refinamento, pendência sem corroboração, continuidade e gráfico.
- Replay de 34.129 quadros em cinco análises, com evidências brutas e arquivos
  de entrada preservados. Starfield manteve o FPS agregado 28.4169918191; UE5
  passou de 49.6855345912 para 50.1070663812 ao excluir períodos sem suporte.
  Outra análise GTA manteve o agregado 29.9567645469. Esses valores são resultados
  dos casos comparados, não garantias de precisão para todos os vídeos.
- Gears: segundos de fonte 132, 133, 473, 474 e 489 passaram a medição nula nos
  intervalos problemáticos; referência 60 continua separada. Prévias dos frames
  7950 e 28429 conferidas com a composição real do exportador.
- 24 comparações de pares novamente decodificados em Gears, Starfield e UE5:
  12 CPU e 12 NVIDIA. Todas as métricas básicas idênticas às da implementação
  anterior, comparando o mesmo backend e as mesmas entradas. Trabalho GPU serializado.
- Executável congelado passou em análise/exportação e contém o novo contrato LLM.
- Instalador completo: instalação nova, upgrade, reinstalação, hashes,
  obsoletos, bloqueio por arquivos em uso/downgrade, atalhos, associação isolada,
  preservação de projeto e desinstalação. Instalação real do usuário preservada.
- Setup público: 553 arquivos conferidos, revisão dos 140 arquivos nativos,
  termos e catálogo antes do aceite, self-test aprovado.

Evidências: `build/tests-0810.log`, `build/retention-0810-replay.json`,
`build/retention-0810-gta-full.json`, `build/retention-0810-pairs.json`,
`build/v0810-preview/validation.json`, `build/full-installer-0810.log`,
`build/installer-0810-public-proof/validation.json`.

Pacote: `AIDA-FPS-Studio-0.8.10-windows-x64-setup.zip`.
Tamanho: 230.518.204 bytes. SHA-256:
`73437a939174f451624ffb868a68e0be21de6c32b0276a168e15d7be47266378`.

Preparado em `E:/dg_apps/site_course/static/aida/`, junto do SHA-256.
Manifesto local atualizado após validação. Publicação remota pelo usuário;
publicar ZIP/SHA antes de ativar o manifesto. Nginx sem alteração.
