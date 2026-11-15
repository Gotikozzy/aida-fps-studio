# AIDA FPS Studio 0.8.14 — abertura progressiva e miniaturas antecipadas

A abertura passa a disponibilizar o monitor e um painel de navegação por tempo
antes de concluir o índice preciso. Até seis miniaturas representativas são
publicadas progressivamente; o primeiro lote precede a varredura completa.
O progresso da indexação e seu cancelamento ficam no painel, sem manter o
workspace preso ao diálogo modal. É possível trocar de vídeo e fechar a janela.

Um índice em cache válido continua sendo o caminho preferencial e dispensa o
lote preliminar. A prévia usa CPU, sem dependências novas, com leitor e cache
separados. Mantém os PTS/time base reais; não calcula número de frame por FPS.
O tempo da imagem pode diferir do pedido e ambos são mostrados. Ao terminar
o índice, a posição solicitada é resolvida pelo índice original. Projetos em
restauração conservam a seleção salva.

Marcas, análise e exportação continuam bloqueadas até o índice validado.
As imagens da prévia representativa nunca entram no analisador/exportador nem
no cache de navegação precisa. Não foram adotadas opções de descarte do decoder.
Não há mudança de qualidade, codec ou preset do vídeo exportado.

Pedidos de monitor cancelam buscas superadas; a varredura cede entre quadros.
Fonte/stat, geração da abertura e pedido impedem imagens de arquivos anteriores,
inclusive ao reabrir o mesmo caminho. Falha de seek, duração desconhecida ou
cache de prévia indisponível não impedem a indexação original. O fechamento
cancela os jobs de mídia antes de aguardar o pool GPU compartilhado.

## Validação

404 testes passaram com o runtime LGPL próprio. Os 17 testes novos cobrem
proveniência e pixels de prévia, cache separado/opcional/corrompido, fonte
alterada, cancelamento, duração desconhecida, índice válido em cache, fallback,
prévia antes do índice, restauração do cursor, pedidos superados, falha de seek,
troca/fechamento durante indexação, VFR e início temporal não zero.

51 arquivos existentes fora de UI/controladores mantiveram hashes idênticos
à 0.8.13. Os 50 módulos presentes em ambos os executáveis também coincidiram;
`dg_fps.__main__` não está nos arquivos PYZ de nenhuma das duas versões.
A DLL NVIDIA permanece idêntica. Isso inclui núcleo analítico, TimestampIndex,
FrameProvider, serviço, backends, relatórios, projetos e apresentação/exportação.

O executável passou no autoteste: análise sintética CPU de 15 FPS, 16 frames
H.264 exportados, interface PT/EN e detecção de Optical Flow/NVENC local.

## Tempos da janela real

Três aberturas por vídeo, cache do aplicativo vazio, cache do SO aquecido,
indexação CPU, Ryzen 7 3800XT / RTX 2080 SUPER. Medianas desde Abrir até o
estado observado na janela Qt. O preparo completo do índice não está incluído
nos tempos de prévia; continua acontecendo em segundo plano.

| Fonte | Primeiro frame | Primeira miniatura | Seis miniaturas | Busca temporal interativa |
| --- | ---: | ---: | ---: | ---: |
| GTA VI | 0,064 s | 0,112 s | 0,235 s | 0,051 s |
| Starfield | 0,117 s | 0,203 s | 0,385 s | 0,085 s |
| Gears E-Day | 0,133 s | 0,252 s | 0,640 s | 0,104 s |
| GTA VI 4K / 14,1 GB | 0,310 s | 0,525 s | 1,674 s | 0,281 s |

Reaberturas com o índice salvo levaram 0,246 / 0,291 / 0,350 / 0,446 s até o
índice pronto, respectivamente. Os quatro índices completos coincidiram com as
referências da versão anterior, e os pixels do frame preciso reaberto também.
Os PTS de todas as miniaturas foram encontrados no índice de referência.
Houve uma busca de 1,721 s na primeira rodada do Starfield; as outras foram
0,085 e 0,082 s. Os tempos são específicos desta máquina/corpus, sem garantia
universal nem extrapolação para validação completa de qualquer arquivo.

## Evidências

- `build/tests-0814.xml`, `build/tests-0814.log`, `build/ruff-0814.log`.
- `build/v0814-proof/opening-window.json`: dados e medianas da janela real.
- `build/v0814-proof/core-integrity.json`, `frozen-integrity.json`: integridade.
- `build/self-test-0814-final/self-test.json`: autoteste do executável final.
- `build/v0814-proof/*-opening-pt.png` e `*-ready-en.png`: provas de interface.
- `scripts/validate_progressive_opening.py`: roteiro de abertura/cache/cancelamento.

Decisão de arquitetura: ADR 0054 do projeto de origem. Análise de desempenho
da medição fica para outra etapa; não foi alterada nesta versão.

## Instalador e entrega

Roteiro NSIS de produção aprovado com payload real e identidade isolada:
instalação, upgrade, reinstalação, hashes de todos os arquivos, remoção de
arquivos aposentados, bloqueio de aplicação em uso e de downgrade, atalhos,
associação isolada, preservação de projeto e desinstalação. Instalação real do
usuário preservada. Registro: `build/full-installer-0814.log`.

Instalador: `dist/installer/public/AIDA-FPS-Studio-0.8.14-windows-x64-setup.exe`,
230549283 bytes. SHA-256:
`088e604644821a1bbfdf6f4e52b76978dcccb58b8774b46f1abb489a3ca40b8e`.

ZIP: `AIDA-FPS-Studio-0.8.14-windows-x64-setup.zip`, 230549469 bytes.
SHA-256: `9749c7e8597828313ab0934ff45d413dc6b3ad8a8acffe765649c9ae7c031daf`.
CRC e checksums conferidos; detalhes em `build/v0814-proof/delivery.json`.
Versões FileVersion/ProductVersion confirmadas como 0.8.14.

Portátil: `dist/0.8.14/AIDA-FPS-Studio/AIDA-FPS-Studio.exe`, junto da pasta completa.
Pacotes gerados localmente; manifesto remoto não foi publicado.
