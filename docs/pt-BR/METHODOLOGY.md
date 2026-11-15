# Metodologia de medição

O vídeo é a entrada observável, não telemetria direta da engine. Taxa de captura,
sequência decodificada e cadência de conteúdo são grandezas diferentes. Imagens repetidas
podem decorrer da captura, cena retida ou renderização; atribuição depende de evidência
e incerteza. Um rótulo isolado não demonstra FPS interno.

Preserve PTS/time base e índice de cada frame; identidade da fonte, ROI, versão do
analisador, parâmetros e backend. Trate VFR e timestamps ambíguos explicitamente.
Diferencie medido/inferido/heurístico/manual. Miniaturas não substituem frames de medição.
Resultados inconclusivos continuam inconclusivos; suavização visual não é nova observação.

Defina pergunta e condições de captura, inspecione qualidade, selecione trecho/ROI,
meça, prove visualmente e só então explique. Exporte dados estruturados e contexto.
Reproduza fonte/parâmetros antes de comparar alterações de desempenho.

Licença aberta e assinatura digital não certificam cada conclusão científica. Mudar
limiares, decoder ou algoritmos GPU exige validação, revisão de método/versão e ADR;
isso não faz parte desta release de empacotamento.

[Other language / Outro idioma](../en/METHODOLOGY.md)
