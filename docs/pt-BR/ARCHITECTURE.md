# Arquitetura

Escopo normativo: ../../SPECIFICATION.md. `src/dg_fps` contém o aplicativo; `native`
contém somente a ponte NVIDIA opcional e helpers MIT. O pacote Python `dg_fps` é
mantido por compatibilidade; o produto é AIDA FPS Studio.

Qt Widgets mostra estado e recebe ações. Jobs/controladores assíncronos coordenam
abertura e análise; mídia decodifica/indexa; cadência e evidência geram medições;
apresentação/exportação renderiza entregas. Texto de UI não vira entrada do analisador.
Trabalho pesado fica fora da thread da UI. GPU é serializada e opcional na abertura.

Abertura progressiva gera prévia de navegação e índice autoritativo de frames/PTS,
com finalidades distintas. Análise/exportação aguardam índice preciso. Cache deve
preservar identidade da fonte, parâmetros e proveniência.

A 0.8.15 preserva os fontes de medição importados por manifesto SHA-256 e muda textos
legais, versão e empacotamento. O marcador offline é política de UI/rede: não altera
decodificação, análise ou encode. Consulte ADR 0001 e verify_source_integrity.py.
Detalhes históricos: ../reference/v0.8.14-ARCHITECTURE.md.

[Other language / Outro idioma](../en/ARCHITECTURE.md)
