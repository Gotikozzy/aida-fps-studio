# AIDA FPS Studio 0.8.5 — candidato de fechamento

O núcleo validado de análise permanece intacto. As mudanças desta edição ficam
na interface, no estado do projeto, na entrega e no instalador.

## Correções e acabamento

- Uma única confirmação para substituir a entrega, inclusive no primeiro salvamento.
- Nome, pasta e tipo de entrega persistidos e restaurados no projeto .aida.
- Estado de salvamento visível; comando para mostrar o projeto no Explorador.
- Barra de abertura do vídeo volta ao modo percentual depois de salvar um projeto.
- Exportação concluída e erro de salvamento são tratados separadamente. Os arquivos
  entregues continuam acessíveis; o projeto anterior é preservado e há opção de tentar salvar.
- Fases do processamento identificadas na janela de progresso.
- Destino e atualização da prévia com ícone e texto; menu de trechos corrigido.
- Guia rápido local em português/inglês e cópia explícita de diagnóstico.
- Consulta de atualização não bloqueante ao iniciar, com aviso somente quando
  houver uma versão mais recente. Falha de conexão não interrompe o Studio.
- Imagens de orientação renovadas com a interface e o gráfico atuais.
- Instalador impede downgrade e mantém instalação por usuário, atalhos, associação
  .aida e desinstalação.

## Evidências

- 288 testes passaram; suíte completa registrada em `build/tests-085-release.log`.
- Executável congelado: `build/selftest-085.json/self-test.json`, status passed,
  análise sintética a 15 FPS e exportação H.264 CPU, 16 quadros decodificados.
  Diagnóstico local reconheceu Optical Flow e NVENC na RTX 2080 SUPER.
- O teste também passou no executável extraído do instalador. Os 362 arquivos
  do payload foram conferidos por hash com a distribuição compilada. Evidências
  em `build/installer-085-proof/`.
- Comparação dos executáveis 0.8.4/0.8.5 em `build/core-comparison-085.json`:
  31 módulos protegidos idênticos, incluindo mídia, análise, gráficos e relatórios.
- Capturas nativas reais em `build/studio-real/pt/analysis.png` e `export.png`.
- Roteiro NSIS de produção testado com identidade isolada e payload de teste:
  instalação nova, upgrade, reinstalação, downgrade bloqueado, atalho, associação
  isolada e desinstalação. Evidência em `build/AIDA Installer Test */validation.json`.
  Não substituiu nem removeu a instalação real do usuário. Não equivale a teste
  numa segunda máquina limpa ou com toda a carga de arquivos instalada.
- Página e manifesto preparados no dg_apps; testes locais cobrem ausência de
  release, arquivo ausente, configuração inválida e download da versão publicada.
  HTML e sanfona de ajuda conferidos no navegador local. Não implantados no servidor.

## Distribuição

O titular escolheu software gratuito com código próprio fechado. A decisão está
refletida no aviso desta edição. Minutas bilíngues em `installer/pilot/`.

O instalador entregue continua identificado como QA. Ainda falta completar a
revisão de fontes correspondentes e licenças transitivas para publicação pública.
O manifesto do site permanece desativado para não oferecer um pacote QA como estável.

### Achado concreto a resolver

O avcodec distribuído pelo PyAV 16.1.0 declara em execução “LGPL version 3 or later”,
mas sua configuração também lista `--enable-libx264` e `--enable-libx265`.
Não se presume que essa combinação esteja regularizada apenas pelo texto da DLL.
É necessário identificar a procedência e os termos exatos dessas bibliotecas,
guardar os fontes correspondentes e as instruções de build/substituição aplicáveis.
Os binários não foram trocados para evitar alterar o resultado validado do produto.

Qt/PySide são distribuídos dinamicamente; a edição pública precisa acompanhar as
obrigações LGPL aplicáveis, não apenas o inventário de nomes e versões.

Referências oficiais consultadas:

- [FFmpeg — licenças e distribuição](https://ffmpeg.org/legal.html)
- [Qt — obrigações LGPL](https://www.qt.io/development/open-source-lgpl-obligations)

O ZIP não elimina SmartScreen e esta edição permanece sem assinatura digital.
