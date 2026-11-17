# Manual do usuário

1. Abra uma captura local com **Nova análise** ou retome um projeto `.aida`.
2. Primeiro frame e miniaturas aparecem progressivamente. Aguarde o índice preciso
   para marcar medições, analisar ou exportar.
3. Selecione trechos adequados à pergunta e registre condições de captura.
4. Execute CPU ou NVIDIA compatível. Inspecione evidências, confiança e avisos.
5. Salve o projeto e preserve acesso ao vídeo original; projeto não é cópia do vídeo.
6. Exporte a apresentação e confira a entrega antes de publicar conclusões.

Prefira captura original, taxa estável e pouca recompressão. Transições, carregamento,
overlays e limitações da captura influenciam a interpretação. Compare separadamente
FPS da captura e cadência do conteúdo. Intervalo inconclusivo não é medição da engine.
Consulte a [metodologia](METHODOLOGY.md).

Preferências controlam idioma, armazenamento e cache. Prefira limpar cache pelo app,
preservando projetos e vídeos. GPU incompatível/ausente não impede CPU. Logs e diagnósticos
são locais; revise caminhos antes de compartilhar. Atualizações: [privacidade](../../PRIVACY.md).

## Timeline e trechos

A área Análise contém projeto/trechos, monitor, resultados e timeline. Redimensione os
painéis conforme necessário; **Exibir → Restaurar painéis** redefine a disposição.
Espaço reproduz/pausa e as setas navegam por quadros. Arraste na faixa de trechos para
criar uma seleção, nas alças para ajustar ou no corpo para mover. Sobreposições são
rejeitadas. Com a timeline em foco, **I** marca início e **O** cria o trecho no fim.
Delete remove a seleção; F2 ou duplo clique renomeia. Ctrl+roda ou Zoom muda a escala.
Ctrl+Z e Ctrl+Shift+Z desfazem/refazem edições de trechos.

**Analisar trechos** processa as seleções incluídas. Alterar trechos invalida a análise
anterior. Mudanças de apresentação não alteram medições. Examine resumo, captura,
referência, cobertura e avisos em conjunto. Inconclusivo não é zero FPS; valor pontilhado
ou projetado no gráfico não é nova observação.

## Projetos e recuperação

Ctrl+S salva; Ctrl+Shift+S salva outro `.aida`. Projetos armazenam referências à origem,
seleções, configurações e relatórios disponíveis. Vídeo e caches ficam externos;
preserve projeto e vídeo ao mover ou fazer backup. Se a origem mudou de pasta, indique
sua localização quando solicitado. A conferência usa tamanho e data de modificação,
não autenticação criptográfica do conteúdo. Origens alteradas exigem nova análise.

O salvamento usa temporário seguido de substituição. Projetos recentes e recuperação
local ficam em Início. Trocar com alterações pendentes oferece salvar, descartar ou
cancelar. Exportar resultado antigo não aplica silenciosamente um novo analisador;
solicite outra análise para aplicar uma metodologia atualizada.

## Formatos de exportação

Em **Exportação**, escolha nome, destino, idioma, codificação e conteúdo. Atualize a prévia
após mudar seleções, referência ou idioma. Se necessário, a exportação analisa antes;
resultados válidos podem ser reutilizados. Cancelar interrompe a operação pendente.

| Conteúdo | Entrega |
|---|---|
| Vídeo e relatório LLM | MP4 H.264 1080p sem áudio e JSON estruturado |
| Somente vídeo | MP4 sem áudio |
| Somente relatório LLM | JSON; não inicia codificação de vídeo |

O relatório LLM contém medições, cobertura, decisões e orientações; não consulta uma LLM.
Relatórios/mapas intermediários ficam no armazenamento de projetos do aplicativo.
Confira os arquivos após exportar. Referências devem respeitar a taxa nominal da captura:
59,94 admite referência de 60 FPS, por exemplo. Referência é configuração de comparação/
exibição, não imposição de resultado. Para quadros ilegíveis, use somente relatório ou
ajuste os trechos para obter sequência completa no MP4. Lacunas separam comparações.

## Resolução de problemas

| Sintoma | Ação |
|---|---|
| Análise indisponível na abertura | Aguarde o índice preciso; miniaturas não indicam que a medição está pronta. |
| Miniaturas ausentes | Use **Exibir → Gerar miniaturas novamente**. |
| Navegação lenta | Use **Exibir → Otimizar prévia** perto do cursor, por CPU ou NVIDIA disponível. Os tempos de medição continuam sendo do original. |
| Suspeita de índice desatualizado | Use **Arquivo → Cache de índices → Reindexar vídeo atual**; analise novamente se os tempos mudarem. |
| Cache ocupando espaço | Use **Arquivo → Cache de índices → Limpar cache de todos os vídeos**. Preserve projetos/originais; o índice aberto fica em memória. |
| NVIDIA indisponível | Confira o diagnóstico nas Preferências e use CPU. |
| Aviso de editor | Confira origem oficial e SHA-256; veja a [política de distribuição](../../CODE_SIGNING.md). |

Preferências, caches e logs rotativos ficam no perfil Windows. Desinstalar preserva
projetos, preferências/cache e arquivos desconhecidos. Revise caminhos nos diagnósticos
antes de enviar um [relato de erro](https://github.com/Gotikozzy/aida-fps-studio/issues).

[Other language / Outro idioma](../en/USER_GUIDE.md)
