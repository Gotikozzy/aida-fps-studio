"""Presentation-only PT/EN catalog. Stored analysis data never passes through it."""

from __future__ import annotations

import re
import string

from PySide6.QtCore import QLocale
from PySide6.QtWidgets import QComboBox, QListWidget, QPlainTextEdit, QTabWidget, QWidget

LANGUAGE = "pt"
CATALOG = {
    "Prévia disponível · preparando índice preciso": "Preview available · preparing precise index",
    "Prévia disponível · indexação interrompida": "Preview available · indexing interrupted",
    "Prévia representativa · preparando índice preciso": (
        "Representative preview · preparing precise index"
    ),
    "Prévia representativa · posição exata após indexação": (
        "Representative preview · exact position after indexing"
    ),
    ("Miniaturas representativas. Marcas, análise e exportação serão liberadas "
     "quando a indexação terminar."): (
        "Representative thumbnails. Marking, analysis and export become available after indexing."
    ),
    "Cancelar indexação": "Cancel indexing",
    "Preparar índice novamente": "Prepare index again",
    "Índice preciso: %p%": "Precise index: %p%",
    "Navegar por tempo durante a indexação": "Browse by time while indexing",
    "Prévia representativa; o tempo da imagem pode diferir do pedido": (
        "Representative preview; image time may differ from the request"
    ),
    "Pedido: {requested} s · imagem: {actual} s": "Requested: {requested} s · image: {actual} s",
    "Imagem em {seconds} s": "Image at {seconds} s",
    "Buscando prévia por tempo…": "Seeking time-based preview…",
    "Prévia temporal indisponível": "Time preview unavailable",
    "Prévia disponível. Preparando índice preciso…": "Preview available. Preparing precise index…",
    "Prévia temporal indisponível. A indexação continua.": (
        "Time preview unavailable. Indexing continues."
    ),
    "O vídeo mudou durante a preparação da prévia": "The video changed while preparing the preview",
    "O vídeo mudou durante a abertura": "The video changed while opening",
    "O vídeo mudou durante a indexação.": "The video changed during indexing.",
    "Atualização disponível": "Update available",
    "Atualizar AIDA FPS Studio": "Update AIDA FPS Studio",
    "Baixar e atualizar": "Download and update",
    "Baixando atualização {version}…": "Downloading update {version}…",
    "Verificando e preparando a atualização…": "Verifying and preparing the update…",
    "Atualização não concluída": "Update not completed",
    (
        "A versão {latest} do AIDA FPS Studio está disponível. "
        "Você está usando a versão {current}.\n\n"
        "Deseja baixar a atualização e abrir o instalador? "
        "O Studio será fechado para atualizar."
    ): (
        "AIDA FPS Studio {latest} is available. You are using version {current}.\n\n"
        "Would you like to download the update and open the installer? "
        "The Studio will close to update."
    ),
    (
        "Não foi possível baixar ou verificar a atualização. "
        "O Studio continua disponível. Tente novamente mais tarde "
        "ou baixe o instalador na página do AIDA."
    ): (
        "The update could not be downloaded or verified. The Studio is still available. "
        "Try again later or download the installer from the AIDA website."
    ),
    (
        "Não foi possível abrir o instalador. "
        "Tente novamente ou baixe a atualização na página do AIDA."
    ): (
        "The installer could not be opened. "
        "Try again or download the update from the AIDA website."
    ),
    "Visão geral": "Overview",
    "Termos do AIDA": "AIDA terms",
    "Licença do AIDA": "AIDA license",
    "Componentes de terceiros": "Third-party components",
    (
        "Código aberto sob Apache-2.0. Você pode usar o AIDA para análises pessoais "
        "ou comerciais. Seus vídeos e projetos continuam seus."
    ): (
        "Open source under Apache-2.0. You can use AIDA for personal "
        "or commercial analysis. Your videos and projects remain yours."
    ),
    (
        "Selecione um documento na lista para ler os termos completos. "
        "A busca localiza documentos e componentes."
    ): (
        "Select a document from the list to read the complete terms. "
        "Search finds documents and components."
    ),
    (
        "O AIDA utiliza Qt/PySide/Shiboken e FFmpeg sob LGPL, além de outros componentes "
        "com licenças próprias. Os textos completos, avisos, fontes e instruções de "
        "substituição acompanham a instalação. Os termos do AIDA não restringem esses direitos."
    ): (
        "AIDA uses LGPL Qt/PySide/Shiboken and FFmpeg, along with other components under "
        "their own licenses. Complete texts, notices, sources and replacement instructions "
        "accompany the installation. AIDA terms do not restrict these rights."
    ),
    "Dicas de captura e análise": "Capture and analysis tips",
    "Qualidade além da resolução": "Quality beyond resolution",
    "Bitrate também importa": "Bitrate matters too",
    "Uma gravação 1080p bem codificada pode preservar mais detalhes em movimento "
    "que uma 4K muito comprimida. O bitrate, o codec e a cena influenciam o resultado.": (
        "A well-encoded 1080p recording can preserve more detail in motion than heavily "
        "compressed 4K. Bitrate, codec, and scene content all affect the result."
    ),
    "Mesmo recorte · 1080p a 12 Mb/s à esquerda · 4K a 2 Mb/s à direita": (
        "Same crop · 1080p at 12 Mb/s on the left · 4K at 2 Mb/s on the right"
    ),
    "Grave direto do console": "Record from your console",
    "Use o arquivo original": "Use the original recording",
    "Use a gravação original do Xbox Series S, Series X, PS5 ou PS5 Pro. Para organizar "
    "a sessão, prefira clipes de até 15 a 20 minutos, conforme as opções do seu console.": (
        "Use the original Xbox Series S, Series X, PS5, or PS5 Pro recording. "
        "For easier organization, aim for clips up to 15–20 minutes, within your console's options."
    ),
    "Exemplo de gameplay usada em uma análise do AIDA": "Gameplay used in an AIDA analysis",
    "Um minuto bem escolhido": "Make every minute count",
    "Separe as cenas importantes": "Pick out the key scenes",
    "Um minuto de uma cena importante pode valer mais que uma hora de gameplay. "
    "Separe combate, travessia e movimentos de câmera em trechos para analisar cada situação.": (
        "One minute of a key scene can tell you more than an hour of gameplay. "
        "Mark combat, traversal, and camera movements as separate ranges to analyze each one."
    ),
    "Trechos nomeados na timeline do AIDA": "Named ranges in the AIDA timeline",
    "Escolha a taxa pela meta": "Match capture rate to target",
    "Taxa da captura e FPS do jogo": "Capture rate and in-game FPS",
    "Uma captura a 60 FPS pode registrar um jogo a 30 FPS, com quadros repetidos "
    "esperados. Para avaliar a meta de 120 FPS, use uma captura que registre acima de 60 FPS.": (
        "A 60 FPS recording can capture a game running at 30 FPS, with expected repeated "
        "frames. To evaluate a 120 FPS target, use a recording that captures above 60 FPS."
    ),
    "Exemplo testado · 40 FPS medidos em uma captura a 120 FPS": (
        "Tested example · 40 FPS measured in a 120 FPS recording"
    ),
    "Aprenda a ler o pontilhado": "Read the dotted line",
    "Identifique trechos inconclusivos": "Spot inconclusive intervals",
    "No gráfico exportado, a linha sólida acompanha a medição. O pontilhado mantém "
    "a continuidade visual quando a medição é inconclusiva.": (
        "In the exported chart, the solid line follows the measurement. The dotted "
        "line keeps the graph continuous where the measurement is inconclusive."
    ),
    "Recorte do gráfico com medição e projeção pontilhada": (
        "Chart crop showing measured FPS and the dotted projection"
    ),
    "Assistir ao canal Detonando Gueek": "Watch the Detonando Gueek channel",
    "Autor": "Author",
    "Ajuda e downloads do AIDA": "AIDA help and downloads",
    "Central de ajuda online": "Online help center",
    "Verificar atualizações": "Check for updates",
    "Consultando o servidor de atualizações…": "Checking for updates…",
    "Versão {version} disponível na página do AIDA.": (
        "Version {version} is available on the AIDA website."
    ),
    "Nenhuma atualização disponível.": "No update available.",
    "A consulta de atualizações ainda não está disponível no servidor.": (
        "The update check is not yet available on the server."
    ),
    "O servidor retornou uma informação de versão inválida.": (
        "The server returned invalid version information."
    ),
    "Não foi possível consultar atualizações. Tente novamente mais tarde.": (
        "Could not check for updates. Try again later."
    ),
    "Otimizar prévia": "Optimize preview",
    "Região atual (CPU)": "Current region (CPU)",
    "Região atual (NVIDIA se disponível)": "Current region (NVIDIA if available)",
    "Cancelar otimização": "Cancel optimization",
    "Otimizando prévia da região…": "Optimizing preview for this region…",
    "Otimizando prévia da região… {percent}%": "Optimizing preview for this region… {percent}%",
    "NVIDIA indisponível para a prévia. Tentando pela CPU…": (
        "NVIDIA preview unavailable. Trying CPU…"
    ),
    "Otimização da prévia cancelada.": "Preview optimization cancelled.",
    "Prévia otimizada (CPU).": "Preview optimized (CPU).",
    "Prévia otimizada (NVIDIA).": "Preview optimized (NVIDIA).",
    "Prévia otimizada indisponível. Usando o original.": (
        "Optimized preview unavailable. Using the original."
    ),
    "Buscando quadro selecionado…": "Loading selected frame…",
    "Quadro selecionado indisponível": "Selected frame unavailable",
    "Miniaturas indisponíveis: {count}": "Unavailable thumbnails: {count}",
    "Quadro indisponível. {message}": "Frame unavailable. {message}",
    "Quadro {frame} indisponível na seleção.": "Frame {frame} is unavailable in the selection.",
    "Leitura parcial · {count} quadros ilegíveis": "Partial read · {count} unreadable frames",
    "Nenhum quadro legível nos trechos selecionados.": "No readable frames in the selected ranges.",
    "A seleção contém quadros ilegíveis. Escolha Somente relatório LLM "
    "ou ajuste os trechos para exportar o vídeo.": (
        "The selection contains unreadable frames. Choose LLM report only "
        "or adjust the ranges to export the video."
    ),
    "Cache de índices": "Index cache",
    "Reindexar vídeo atual…": "Reindex current video…",
    "Limpar cache de todos os vídeos…": "Clear cache for all videos…",
    "Reindexar vídeo atual": "Reindex current video",
    "Limpar cache de índices": "Clear index cache",
    "Apagar o índice salvo deste vídeo e reindexar agora? "
    "Se os tempos mudarem, será necessário analisar novamente.": (
        "Remove this video's cached index and reindex now? "
        "If the timing changes, a new analysis will be needed."
    ),
    "Apagar os índices de todos os vídeos? "
    "Os índices serão recriados conforme você abrir os vídeos.": (
        "Remove the cached indexes for all videos? Indexes will be rebuilt as you open videos."
    ),
    "Reindexando vídeo…": "Reindexing video…",
    "Reindexação concluída.": "Reindexing complete.",
    "Reindexação interrompida.": "Reindexing stopped.",
    "Não foi possível reindexar": "Could not reindex the video",
    "O vídeo mudou durante a reindexação.": "The video changed during reindexing.",
    "Índice atualizado. Revise os trechos e analise novamente.": (
        "Index updated. Review the ranges and analyze again."
    ),
    "Índice atualizado. Analise novamente.": "Index updated. Analyze again.",
    "Limpando cache de índices…": "Clearing index cache…",
    "Índices removidos: {count}": "Indexes removed: {count}",
    "Alguns índices não puderam ser removidos": "Some indexes could not be removed",
    "Teste NVIDIA": "NVIDIA test",
    "Início": "Home",
    "Testando compatibilidade NVIDIA…": "Testing NVIDIA compatibility…",
    "Pular miniaturas": "Skip thumbnails",
    "Gerar miniaturas novamente": "Retry thumbnails",
    "Miniaturas indisponíveis. Gere novamente pelo menu Exibir.": (
        "Thumbnails unavailable. Retry from the View menu."
    ),
    "Taxa da captura indisponível. Use Automático.": ("Capture rate unavailable. Use Automatic."),
    "Miniaturas puladas. O vídeo está pronto.": "Thumbnails skipped. The video is ready.",
    "Vídeo pronto. Gere as miniaturas pelo menu Exibir.": (
        "Video ready. Retry thumbnails from the View menu."
    ),
    "Pronto: {count} frames. Use I e O para criar um trecho.": (
        "Ready: {count} frames. Use I and O to create a range."
    ),
    "Início marcado. Use O ou o botão direito no fim.": (
        "Start marked. Press O or right-click at the end."
    ),
    "Encerrar novo trecho aqui": "End new range here",
    "Ajustar fim de “{name}” aqui": "Set end of “{name}” here",
    "Limite da captura: {value} FPS": "Capture limit: {value} FPS",
    "Há metas incompatíveis com a captura. Escolha outra meta ou Automático.": (
        "Some targets are incompatible with the capture rate. Choose another target or Automatic."
    ),
    "Atualizar o projeto com esta análise?": "Update the project with this analysis?",
    "Salvar alterações antes de trocar de projeto?": "Save changes before switching projects?",
    "Início do trecho": "Range start",
    "Iniciar trecho aqui": "Start range here",
    "Encerrar trecho aqui": "End range here",
    "Apagar trecho": "Delete range",
    "Início marcado. Clique com o botão direito no fim.": (
        "Start marked. Right-click the end of the range."
    ),
    "Marque o início do trecho primeiro.": "Mark the range start first.",
    "Escolha a entrega. A análise será feita automaticamente ao exportar.": (
        "Choose your delivery. Analysis will run automatically when you export."
    ),
    "Exportação": "Export",
    "Arraste aqui para selecionar um trecho": "Drag here to select a range",
    "Selecione um trecho na timeline": "Select a range on the timeline",
    "Média medida • FPS": "Measured average • FPS",
    "Resultados de versões anteriores": "Results from earlier versions",
    "Abrir pasta da entrega": "Open delivery folder",
    "Trecho selecionado": "Selected range",
    "Nova análise": "New analysis",
    "Nova análise…": "New analysis…",
    "Abrir análise…": "Open analysis…",
    "Abrir análise": "Open analysis",
    "Salvar análise": "Save analysis",
    "Salvar análise como…": "Save analysis as…",
    "Análises recentes": "Recent analyses",
    "Nenhuma análise recente": "No recent analyses",
    "Preferências": "Preferences",
    "Arquivo": "File",
    "Editar": "Edit",
    "Análise": "Analysis",
    "Exibir": "View",
    "Ajuda": "Help",
    "Sair": "Exit",
    "Desfazer": "Undo",
    "Refazer": "Redo",
    "Projeto": "Project",
    "Monitor de vídeo": "Video monitor",
    "Resultados": "Results",
    "Propriedades": "Properties",
    "FPS medidos": "Measured FPS",
    "Captura": "Capture",
    "Meta": "Target",
    "Captura: —": "Capture: —",
    "Meta: —": "Target: —",
    "Aguardando análise": "Waiting for analysis",
    "FPS ao longo do tempo": "FPS over time",
    "Análise concluída": "Analysis complete",
    "Analisar trechos": "Analyze ranges",
    "Selecione e ajuste os trechos na timeline. I e O marcam início e fim.": (
        "Select and adjust ranges on the timeline. I and O mark in and out."
    ),
    "Prévia da apresentação": "Presentation preview",
    "Após analisar, escolha o conteúdo da entrega.": "After analysis, choose what to deliver.",
    "Conteúdo da entrega": "Delivery contents",
    "Vídeo e relatório LLM": "Video and LLM report",
    "Somente vídeo": "Video only",
    "Somente relatório LLM": "LLM report only",
    "Nome da entrega": "Delivery name",
    "Destino": "Destination",
    "Escolher pasta…": "Choose folder…",
    "Arquivos técnicos ficam no projeto. Entrega somente dos itens escolhidos.": (
        "Technical files stay in the project. Deliveries contain only the selected items."
    ),
    "Exportar entrega": "Export delivery",
    "Atualizar prévia": "Update preview",
    "Sua próxima análise começa aqui.": "Your next analysis starts here.",
    "Abra um vídeo, selecione os trechos e transforme a medição em uma apresentação.": (
        "Open a video, select ranges and turn measurements into a presentation."
    ),
    "Recuperar última análise": "Recover last analysis",
    "Preparando operação…": "Preparing operation…",
    "Abrindo e indexando vídeo…": "Opening and indexing video…",
    "Renomear trecho": "Rename range",
    "Renomear trecho…": "Rename range…",
    "Nome": "Name",
    "Importar vídeo…": "Import video…",
    "Restaurar painéis": "Reset panels",
    "Diagnóstico de compatibilidade": "Compatibility diagnostics",
    "Sobre AIDA FPS Studio": "About AIDA FPS Studio",
    "Análise de FPS e cadência visual • versão {version}": (
        "FPS and visual cadence analysis • version {version}"
    ),
    "Localizar vídeo original": "Locate original video",
    "Vídeo alterado • analisar novamente": "Video changed • analyze again",
    "O vídeo foi alterado. Selecione os trechos novamente.": (
        "The video changed. Select the ranges again."
    ),
    "Análise salva": "Analysis saved",
    "Preparando prévia": "Preparing preview",
    "Prévia atualizada": "Preview updated",
    "Entrega salva e verificada": "Delivery saved and verified",
    "Escolha um nome de arquivo válido.": "Choose a valid filename.",
    "Substituir arquivos existentes?": "Replace existing files?",
    "Timeline visual de análise": "Visual analysis timeline",
    "Selecionar intervalo • arraste na timeline": "Select range • drag on the timeline",
    "Zoom da timeline • Ctrl + roda do mouse": "Timeline zoom • Ctrl + mouse wheel",
    "Vídeo": "Video",
    "Trechos": "Ranges",
    "Preparando relatório LLM": "Preparing LLM report",
    "Gravando entrega": "Saving delivery",
    "Restaurando resultados": "Restoring results",
    "Abrir pasta do vídeo": "Open video folder",
    "Finalizando o arquivo MP4": "Finalizing MP4 file",
    "Vídeo codificado; preparando a gravação": "Video encoded; preparing to save",
    "Verificando o arquivo MP4": "Verifying MP4 file",
    "Sincronizando a gravação do vídeo": "Synchronizing video file",
    "Gravando o vídeo na pasta escolhida": "Saving video to the selected folder",
    "Registrando o vídeo nos relatórios": "Registering video in reports",
    "Vídeo salvo e verificado: {path}": "Video saved and verified: {path}",
    "Vídeo salvo com aviso": "Video saved with a warning",
    "O MP4 não foi encontrado no destino": "The MP4 was not found at the destination",
    "O MP4 foi salvo em {path}, mas os relatórios não puderam ser atualizados: {reason}": (
        "The MP4 was saved to {path}, but reports could not be updated: {reason}"
    ),
    "Não foi possível gravar o vídeo em {path}: {reason}": (
        "Unable to save the video to {path}: {reason}"
    ),
    "Não foi possível validar o MP4 em {path}: {reason}": (
        "Unable to verify the MP4 at {path}: {reason}"
    ),
    "Usado ao abrir o próximo vídeo. A CPU preserva compatibilidade e metadados.": (
        "Used when opening the next video. CPU preserves compatibility and metadata."
    ),
    "índice salvo": "saved index",
    "Indexação": "Indexing",
    "Indexar vídeo": "Index video",
    "Meta do conteúdo": "Content target",
    "Metas por trecho…": "Targets by segment…",
    "Metas por trecho": "Targets by segment",
    "Automático — cadência observada": "Automatic — observed cadence",
    "Personalizada": "Custom",
    "Referência de apresentação; não altera a medição.": (
        "Display reference; does not change the measurement."
    ),
    "Referências do conteúdo (apresentação):": "Content references (display):",
    "indeterminada": "undetermined",
    "manual": "manual",
    "inferida": "inferred",
    "Próximo da referência": "Near reference",
    "Abaixo da referência": "Below reference",
    "Acima da referência": "Above reference",
    "Sem referência": "No reference",
    "Captura limita a comparação": "Capture limits comparison",
    "Referência": "Reference",
    ("AIDA FPS Studio — FPS e cadência visual"): ("AIDA FPS Studio — FPS and visual cadence"),
    ("Abrir vídeo"): ("Open video"),
    ("Pasta dos resultados…"): ("Results folder…"),
    ("Pasta dos resultados"): ("Results folder"),
    ("Abrir resultados"): ("Open results"),
    ("Nenhum vídeo aberto"): ("No video open"),
    ("Prévia do vídeo"): ("Video preview"),
    ("Abra um vídeo para analisar FPS e cadência"): ("Open a video to analyze FPS and cadence"),
    ("Processar análise"): ("Analysis processing"),
    ("Codificar exportação"): ("Video encoding"),
    ("CPU — compatibilidade"): ("CPU — compatibility"),
    ("Automático"): ("Automatic"),
    ("NVIDIA — opcional"): ("NVIDIA — optional"),
    ("Exportar vídeo com gráfico — 1080p"): ("Export video with chart — 1080p"),
    ("Exportar vídeo com gráfico"): ("Export video with chart"),
    ("Exportar vídeo"): ("Export video"),
    ("Cancelar"): ("Cancel"),
    ("FPS inferido do conteúdo capturado. Cena estática pode ser inconclusiva."): (
        "FPS inferred from captured content. Static scenes may be inconclusive."
    ),
    ("A prévia e o vídeo exportado não incluem áudio."): (
        "Preview and exported video have no audio."
    ),
    ("Vídeos (*.mp4 *.mkv *.mov *.avi *.webm *.m4v);;Todos (*)"): (
        "Videos (*.mp4 *.mkv *.mov *.avi *.webm *.m4v);;All files (*)"
    ),
    ("Pronto: {count} frames. Marque início (I) e fim (O) e adicione o trecho."): (
        "Ready: {count} frames. Mark in (I) and out (O), then add the segment."
    ),
    ("Analisando FPS e cadência…"): ("Analyzing FPS and cadence…"),
    ("Analisar FPS"): ("Analyze FPS"),
    ("Substituir vídeo"): ("Replace video"),
    ("Substituir {name}?"): ("Replace {name}?"),
    ("Operação interrompida"): ("Operation stopped"),
    ("Não foi possível concluir"): ("Unable to complete"),
    ("Operação cancelada"): ("Operation canceled"),
    ("Não foi possível ler o vídeo"): ("Unable to read video"),
    ("Vídeo indisponível"): ("Video unavailable"),
    ("Análise concluída. Confira o resultado e exporte quando desejar."): (
        "Analysis complete. Review the result and export when ready."
    ),
    ("Análise concluída. Confira o resultado antes de exportar."): (
        "Analysis complete. Review the result before exporting."
    ),
    ("Relatórios salvos. Use Abrir resultados para acessar."): (
        "Reports saved. Select Open results to view them."
    ),
    ("FPS do conteúdo: {value}"): ("Content FPS: {value}"),
    ("Captura nominal: {value} FPS"): ("Nominal capture: {value} FPS"),
    ("Cobertura observável: {value}"): ("Observable coverage: {value}"),
    ("Processamento: {value}"): ("Processing: {value}"),
    ("Vídeo exportado: {value}"): ("Video exported: {value}"),
    ("inconclusivo"): ("inconclusive"),
    ("Seleção de trechos para FPS e cadência"): ("Segment selection for FPS and cadence"),
    ("Início: —   Fim: —"): ("In: —   Out: —"),
    ("Início: {start}   Fim: {end}"): ("In: {start}   Out: {end}"),
    ("Marque início e fim de um ou mais trechos."): ("Mark in and out for one or more segments."),
    ("O resultado da análise aparecerá aqui."): ("Analysis results will appear here."),
    ("Marcar início (I)"): ("Mark in (I)"),
    ("Marcar fim (O)"): ("Mark out (O)"),
    ("Adicionar trecho"): ("Add segment"),
    ("Incluir o trecho marcado (Ctrl+Shift+A)"): ("Add marked segment (Ctrl+Shift+A)"),
    ("Remover trecho"): ("Remove segment"),
    ("Limpar trechos"): ("Clear segments"),
    ("Analisar FPS dos trechos"): ("Analyze segment FPS"),
    ("Trechos incluídos na medição"): ("Segments included in measurement"),
    ("Marque início e fim antes de adicionar o trecho."): (
        "Mark in and out before adding a segment."
    ),
    ("O trecho precisa conter pelo menos dois frames."): (
        "A segment must contain at least two frames."
    ),
    ("Esse trecho se sobrepõe a uma seleção existente."): (
        "This segment overlaps an existing selection."
    ),
    ("{count} trecho(s) incluído(s)."): ("{count} segment(s) included."),
    ("Trecho {number}: frames {details}"): ("Segment {number}: frames {details}"),
    ("Trecho {number}: {value} FPS"): ("Segment {number}: {value} FPS"),
    ("Adicione pelo menos um trecho antes da análise."): (
        "Add at least one segment before analysis."
    ),
    ("Miniaturas da timeline"): ("Timeline thumbnails"),
    ("Clique para navegar até um ponto do vídeo"): ("Click to seek to a point in the video"),
    ("Gerando miniaturas…"): ("Generating thumbnails…"),
    ("Miniaturas"): ("Thumbnails"),
    ("Cadência visual"): ("Visual cadence"),
    (
        "Azul: atualização; cinza: retenção regular ou sinal insuficiente; laranja: "
        "retenção prolongada"
    ): ("Blue: update; gray: regular hold or insufficient signal; orange: extended hold"),
    ("Ir para frame por índice"): ("Go to frame by index"),
    ("Digite o índice e confirme com Enter • alternativa: Ctrl+G"): (
        "Enter a frame index and press Enter"
    ),
    ("Frame anterior (Seta esquerda)"): ("Previous frame (Left arrow)"),
    ("Frame anterior"): ("Previous frame"),
    ("Reproduzir ou pausar (Espaço/K)"): ("Play or pause (Space)"),
    ("Reproduzir ou pausar"): ("Play or pause"),
    ("Próximo frame (Seta direita)"): ("Next frame (Right arrow)"),
    ("Próximo frame"): ("Next frame"),
    ("Timeline de frames"): ("Frame timeline"),
    ("Seleciona um frame do vídeo usando o índice temporal real"): (
        "Selects a video frame using the actual timestamp index"
    ),
    ("Timeline de frames — arraste para navegar"): ("Frame timeline — drag to seek"),
    ("Início · I"): ("In · I"),
    ("Fim · O"): ("Out · O"),
    ("Marcar início no processo ativo (I)"): ("Mark in for the active selection (I)"),
    ("Marcar fim no processo ativo (O)"): ("Mark out for the active selection (O)"),
    ("TIMELINE  ·  navegação precisa por frame e tempo da captura"): (
        "TIMELINE  ·  precise navigation by frame and capture time"
    ),
    ("PAUSADO"): ("PAUSED"),
    ("AVANÇO"): ("FORWARD"),
    ("REVERSO"): ("REVERSE"),
    ("AVANÇO {speed}x"): ("FORWARD {speed}x"),
    ("REVERSO {speed}x"): ("REVERSE {speed}x"),
    ("Frame {index} — carregando…"): ("Frame {index} — loading…"),
    ("Frame {index} — selecionado"): ("Frame {index} — selected"),
    ("Lendo metadados"): ("Reading metadata"),
    ("Decodificando primeiro frame"): ("Decoding first frame"),
    ("Vídeo aberto"): ("Video opened"),
    ("Indexando frame {index}"): ("Indexing frame {index}"),
    ("Índice concluído: {count} frames"): ("Index complete: {count} frames"),
    ("Miniatura {index} de {total}"): ("Thumbnail {index} of {total}"),
    ("Decodificando frame {index}"): ("Decoding frame {index}"),
    ("Frame {index} pronto"): ("Frame {index} ready"),
    ("Analisando: {backend}"): ("Analyzing: {backend}"),
    ("Analisando Trecho {number}: frame {index}"): ("Analyzing Segment {number}: frame {index}"),
    ("Comparando frame {index}"): ("Comparing frame {index}"),
    ("Cadência concluída: {count} frames"): ("Cadence complete: {count} frames"),
    ("Cadência concluída: {count} frames selecionados"): (
        "Cadence complete: {count} selected frames"
    ),
    ("Gerando analysis.json e report.json"): ("Generating analysis.json and report.json"),
    ("Renderizando vídeo 1080p: {details}"): ("Rendering 1080p video: {details}"),
    ("Vídeo gráfico 1080p concluído"): ("1080p chart video complete"),
    ("A aceleração falhou; reiniciando a exportação pela CPU"): (
        "Acceleration failed; restarting export on CPU"
    ),
    ("Selecione pelo menos um trecho"): ("Select at least one segment"),
    ("Os nomes dos trechos precisam ser únicos"): ("Segment names must be unique"),
    ("Trecho fora do vídeo ou com menos de dois frames"): (
        "Segment out of bounds or shorter than two frames"
    ),
    ("Os trechos não podem se sobrepor"): ("Segments cannot overlap"),
    ("Modo de exportação inválido"): ("Invalid export mode"),
    ("O vídeo mudou durante a análise; abra o arquivo novamente"): (
        "The video changed during analysis; reopen it"
    ),
    ("O vídeo foi alterado. Abra e analise novamente antes de exportar."): (
        "The video changed. Reopen and analyze it before exporting."
    ),
    ("O vídeo de saída não pode substituir o vídeo original"): (
        "The output cannot replace the original video"
    ),
    ("O vídeo mudou durante a exportação; analise novamente"): (
        "The video changed during export; analyze it again"
    ),
    ("Tempos não crescentes no trecho; exportação interrompida"): (
        "Non-increasing segment timestamps; export stopped"
    ),
    ("Duração inválida no fim do trecho"): ("Invalid duration at end of segment"),
    ("Ponte NVIDIA ausente no pacote. Reinstale o aplicativo ou selecione CPU."): (
        "NVIDIA bridge missing. Reinstall the application or select CPU."
    ),
    ("NVIDIA indisponível: {detail}. Selecione CPU ou Automático."): (
        "NVIDIA unavailable: {detail}. Select CPU or Automatic."
    ),
    ("Idioma"): ("Language"),
    ("Sistema (automático)"): ("System (automatic)"),
    ("Testar NVIDIA"): ("Test NVIDIA"),
    ("Compatibilidade NVIDIA"): ("NVIDIA compatibility"),
    ("Ainda não testado. O modo Automático verifica a compatibilidade ao analisar."): (
        "Not tested yet. Automatic mode checks compatibility when analyzing."
    ),
    ("Verificando suporte NVIDIA…"): ("Checking NVIDIA support…"),
    ("Testando Optical Flow: {name}"): ("Testing Optical Flow: {name}"),
    ("Testando codificação NVIDIA…"): ("Testing NVIDIA encoding…"),
    ("Teste NVIDIA concluído"): ("NVIDIA test complete"),
    ("Ponte incluída: {value}"): ("Bundled bridge: {value}"),
    ("Driver NVIDIA: {value}"): ("NVIDIA driver: {value}"),
    ("Análise com NVIDIA: {value}"): ("NVIDIA analysis: {value}"),
    ("Codificação com NVIDIA: {value}"): ("NVIDIA encoding: {value}"),
    ("Disponível"): ("Available"),
    ("Indisponível"): ("Unavailable"),
    ("Aprovado"): ("Passed"),
    ("Não aprovado"): ("Not supported"),
    ("Reinstale o pacote completo do AIDA FPS Studio para restaurar a ponte."): (
        "Reinstall the complete AIDA FPS Studio package to restore the bridge."
    ),
    ("Instale ou atualize o driver de vídeo NVIDIA e teste novamente."): (
        "Install or update the NVIDIA display driver and test again."
    ),
    ("Nenhuma GPU NVIDIA detectada pelo driver."): ("No NVIDIA GPU detected by the driver."),
    ("Optical Flow não passou no teste. Use CPU ou atualize o driver e teste novamente."): (
        "Optical Flow did not pass. Use CPU or update the driver and test again."
    ),
    ("NVENC indisponível. A exportação continua disponível pela CPU."): (
        "NVENC unavailable. Video export remains available on CPU."
    ),
    ("CPU continua disponível para análise e exportação."): (
        "CPU remains available for analysis and export."
    ),
    ("Detalhes: {value}"): ("Details: {value}"),
    ("Cadência visual (inclui retenções): {value} FPS"): (
        "Visual cadence (includes holds): {value} FPS"
    ),
    ("Tempo ambíguo: {value} s"): ("Ambiguous time: {value} s"),
    ("Retenções prolongadas: {value} s"): ("Prolonged holds: {value} s"),
    ("Retenção não identifica pausa nem queda do jogo."): (
        "An image hold does not identify a pause or game frame-rate drop."
    ),
}


CATALOG.update(
    {
        "Salvando projeto…": "Saving project…",
        "Salvar alterações antes de fechar?": "Save changes before closing?",
        "Aguarde a operação terminar ou cancele pelo progresso.": (
            "Wait for the operation to finish or cancel it in the progress window."
        ),
        "Projetos recentes": "Recent projects",
        "Abrir projeto": "Open project",
        "Seus projetos salvos aparecem aqui. Comece em Nova análise ou abra um arquivo .aida.": (
            "Your saved projects appear here. Start with New analysis or open an .aida file."
        ),
        "O que deseja exportar?": "What would you like to export?",
        "Nome dos arquivos": "File name",
        "Salvar em": "Save to",
        "Exportar arquivos": "Export files",
        "Salvar projeto": "Save project",
        "Salvar projeto como…": "Save project as…",
        "Abrindo e preparando vídeo…": "Opening and preparing video…",
        "Dica recolhida. Pressione Espaço para abrir.": "Tip collapsed. Press Space to open.",
        "Dica aberta. Pressione Espaço para fechar.": "Tip expanded. Press Space to close.",
        "Exportação com NVIDIA: {value}": "NVIDIA export: {value}",
        "Reinstale o AIDA FPS Studio para restaurar os arquivos de aceleração.": (
            "Reinstall AIDA FPS Studio to restore the acceleration files."
        ),
        "A aceleração da análise está indisponível. "
        "Use o processador ou atualize o driver NVIDIA e teste novamente.": (
            "Analysis acceleration is unavailable. "
            "Use the processor or update the NVIDIA driver and retry."
        ),
        "Você pode exportar o vídeo usando o processador (CPU).": (
            "You can export the video using the processor (CPU)."
        ),
        "Tire mais de cada captura": "Get more from every recording",
        "SEU PRÓXIMO PASSO": "YOUR NEXT STEP",
        "Marque o trecho. Encontre a queda.": "Pick a scene. Find the drop.",
        "Trechos selecionados na linha do tempo do AIDA": "Selected ranges on the AIDA timeline",
        "Analise só o que importa. Salve o projeto e retome quando quiser.": (
            "Focus on what matters. Save your project and pick up where you left off."
        ),
        "Gravar · Preserve os detalhes": "Record · Keep the detail",
        "Gravar · Use o arquivo original": "Record · Use the original file",
        "Analisar · Foque nas cenas importantes": "Analyze · Focus on key scenes",
        "Gravar · Escolha a captura certa": "Record · Choose the right capture",
        "Entender · Leia o resultado": "Understand · Read the result",
        "Abra a dica para ver o exemplo e as orientações.": (
            "Open this tip for an example and guidance."
        ),
        (
        "Uma captura a 60 FPS pode registrar um jogo a 30 FPS, com quadros repetidos "
        "esperados. A meta de 120 FPS fica disponível em capturas acima de 118 FPS, "
        "incluindo as gravações a 119.88 FPS. Para a meta de 40 FPS, use captura "
        "acima de 58 FPS."
        ): (
            "A 60 FPS recording can capture a 30 FPS game with expected repeated frames. "
            "The 120 FPS target is available for recordings above 118 FPS, including 119.88 FPS. "
            "For the 40 FPS target, use a recording above 58 FPS."
        ),
        (
        "Abra uma captura, marque os trechos e confira o FPS. Salve o projeto "
        "para continuar depois."
        ): (
            "Open a recording, select your scenes and check the FPS. "
            "Save your project to continue later."
        ),
        "Abrir projeto…": "Open project…",
        "Abra um vídeo para começar um novo projeto de análise.": (
            "Open a video to start a new analysis project."
        ),
        "Retome os trechos e resultados de um projeto .aida salvo.": (
            "Resume the ranges and results in a saved .aida project."
        ),
        "1  Abra o vídeo    →    2  Selecione os trechos    →    3  Analise e salve": (
            "1  Open a video    →    2  Select ranges    →    3  Analyze and save"
        ),
        "Marcar início do trecho (I). Depois, marque o fim para adicioná-lo à análise.": (
            "Mark the range start (I). Then mark its end to add it to the analysis."
        ),
        "Marcar fim do trecho (O). O intervalo marcado será incluído na análise.": (
            "Mark the range end (O). The marked range will be added to the analysis."
        ),
        "FPS médio medido no trecho selecionado. Sem seleção, mostra a média da análise.": (
            
        "Average FPS measured in the selected range. With no selection, shows the"
        " analysis average."
        
        ),
        "Taxa de quadros do arquivo gravado. Ela define quais metas a captura permite avaliar.": (
            
        "Frame rate of the recorded file. It determines which targets the "
        "recording can support."
        
        ),
        "FPS de referência para comparar o resultado. Escolher uma meta preserva a medição.": (
            "Reference FPS for comparing the result. Choosing a target preserves the measurement."
        ),
        "Meta de FPS": "FPS target",
        "Use Automático ou escolha o FPS esperado do jogo. "
        "A meta precisa ser compatível com a captura.": (
            "Use Automatic or choose the game's expected FPS. The target must fit the recording."
        ),
        "Vídeo e relatório para IA": "Video and AI-ready report",
        "Apenas relatório para IA": "AI-ready report only",
        (
        "Escolha o que salvar. O relatório reúne medições e contexto em JSON para"
        " usar com uma IA."
        ): (
            "Choose what to save. "
            "The report contains measurements and context in JSON for an AI assistant."
        ),
        "Processamento do vídeo": "Video processing",
        "Define como gerar o vídeo exportado. Automático usa a opção disponível no computador.": (
            "Choose how to create the exported video. "
            "Automatic uses an available option on your computer."
        ),
        "Meça os trechos selecionados e veja o resultado no Studio. Você pode exportar depois.": (
            "Measure the selected ranges and review the result in the Studio. You can export later."
        ),
        "Salve os itens escolhidos. Se necessário, o Studio faz a análise antes de exportar.": (
            "Save your selected outputs. The Studio analyzes the footage first when needed."
        ),
        "Arraste na linha do tempo para criar um trecho. Ajuste as bordas ou use I e O.": (
            "Drag on the timeline to create a range. Adjust its edges or use I and O."
        ),
        "Escolha como analisar. Automático verifica a aceleração disponível. "
        "A CPU funciona sem NVIDIA.": (
            
        "Choose how to analyze. Automatic checks available acceleration. CPU "
        "works without NVIDIA."
        
        ),
        "Preparar vídeo": "Prepare video",
        "Processador (CPU)": "Processor (CPU)",
        "Placa de vídeo NVIDIA": "NVIDIA graphics card",
        "Verificar aceleração gráfica": "Check GPU acceleration",
        "Prepara a navegação ao abrir o próximo vídeo. Escolha CPU ou detecção automática.": (
            "Prepare navigation when opening the next video. Choose CPU or automatic detection."
        ),
        "Arraste na linha do tempo para marcar o trecho que quer analisar.": (
            "Drag on the timeline to mark the range you want to analyze."
        ),
        "Abra um vídeo para começar a análise.": "Open a video to start analyzing.",
        "Trechos prontos. Clique em Analisar trechos.": "Ranges ready. Click Analyze ranges.",
        "Análise concluída. Revise o FPS, salve o projeto ou exporte.": (
            "Analysis complete. Review the FPS, save your project or export."
        ),
    }
)


CATALOG.update(
    {
        "Projetos recentes": "Recent projects",
        "Nenhum projeto recente": "No recent projects",
        "Mostrar projeto na pasta": "Show project in folder",
        "Alterações não salvas": "Unsaved changes",
        "Projeto salvo": "Project saved",
        "Mais opções de trechos": "More range options",
        "Copiar informações de diagnóstico": "Copy diagnostic information",
        "Diagnóstico copiado.": "Diagnostics copied.",
        "Guia rápido": "Quick start guide",
        "Atualização {version} disponível": "Update {version} available",
        "Entrega salva; projeto com alterações não salvas.": (
            "Delivery saved; project has unsaved changes."
        ),
        "Entrega salva": "Delivery saved",
        (
            "Os arquivos foram exportados, mas o projeto não pôde ser salvo. Tentar "
            "salvar o projeto novamente?"
        ): (
            "The files were exported, but the project could not be saved. Try saving the "
            "project again?"
        ),
        "1. Abra o vídeo": "1. Open a video",
        "Use a captura original. A prévia pode ser reduzida sem alterar a análise.": (
            "Use the original recording. Preview quality can be reduced without changing "
            "the analysis."
        ),
        "2. Selecione os trechos": "2. Select ranges",
        (
            "Arraste na timeline ou use I para o início e O para o fim. Delete apaga o "
            "trecho selecionado."
        ): (
            "Drag on the timeline or use I for the start and O for the end. Delete "
            "removes the selected range."
        ),
        "3. Confira a meta": "3. Check the target",
        (
            "A meta serve de referência. Ela não pode superar a taxa que a captura "
            "permite observar."
        ): (
            "The target is a reference. It cannot exceed the rate observable in the "
            "recording."
        ),
        "4. Analise ou exporte": "4. Analyze or export",
        (
            "Você pode analisar no Studio ou ir direto à exportação. Escolha vídeo, "
            "relatório para IA ou ambos."
        ): (
            "Analyze in the Studio or go straight to export. Choose video, an AI report "
            "or both."
        ),
        "5. Salve seu projeto": "5. Save your project",
        (
            "O arquivo .aida guarda os trechos, resultados e opções. Mantenha o vídeo "
            "original disponível para reabrir o projeto."
        ): (
            "The .aida file stores ranges, results and settings. Keep the original video "
            "available when reopening the project."
        ),
    }
)


CATALOG.update({"Exemplo testado · medição limitada à captura original": (
    "Tested example · measurement limited to the original recording"
)})

CATALOG.update({
    "Termos e licenças": "Terms and licenses",
    ("Os componentes de terceiros seguem suas próprias licenças. "
     "Os termos do AIDA não limitam os direitos concedidos por elas."): (
        "Third-party components are governed by their own licenses. "
        "The AIDA terms do not limit the rights they grant."
    ),
    "Buscar documento ou componente…": "Search for a document or component…",
    "Buscar licença": "Search licenses",
    "Documentos de distribuição": "Distribution documents",
    "Texto da licença": "License text",
    "Documentos de distribuição indisponíveis.": "Distribution documents unavailable.",
    "Não foi possível abrir este documento.": "This document could not be opened.",
    "Nenhum documento encontrado.": "No documents found.",
})

def system_language(name: str | None = None) -> str:
    return "pt" if (name or QLocale.system().name()).lower().startswith("pt") else "en"


def set_language(language: str) -> None:
    global LANGUAGE
    if language not in {"pt", "en"}:
        raise ValueError(language)
    LANGUAGE = language


def _pattern(template: str) -> re.Pattern[str]:
    pieces = []
    for literal, name, _, _ in string.Formatter().parse(template):
        pieces.append(re.escape(literal))
        if name:
            pieces.append(f"(?P<{name}>.+?)")
    return re.compile("".join(pieces))


PATTERNS = [(pt, en, _pattern(pt), _pattern(en)) for pt, en in CATALOG.items() if "{" in pt]
REVERSE = {value: key for key, value in CATALOG.items()}


def localize(text: str) -> str:
    direct = CATALOG if LANGUAGE == "en" else REVERSE
    if text in direct:
        return direct[text]
    if "\n" in text:
        return "\n".join(localize(line) for line in text.split("\n"))
    segment = re.fullmatch(r"(Trecho|Segment) (\d+)(:.*)?", text)
    if segment:
        prefix = "Segment" if LANGUAGE == "en" else "Trecho"
        return f"{prefix} {segment[2]}{segment[3] or ''}"
    for pt, en, pt_pattern, en_pattern in PATTERNS:
        match = (pt_pattern if LANGUAGE == "en" else en_pattern).fullmatch(text)
        if match:
            values = match.groupdict()
            if "value" in values:
                values["value"] = direct.get(values["value"], values["value"])
            return (en if LANGUAGE == "en" else pt).format_map(values)
    return text


def translate_tree(root: QWidget) -> None:
    """Refresh existing presentation text without reconstructing application state."""
    for widget in [root, *root.findChildren(QWidget)]:
        for getter, setter in (
            ("toolTip", "setToolTip"),
            ("accessibleName", "setAccessibleName"),
            ("accessibleDescription", "setAccessibleDescription"),
            ("windowTitle", "setWindowTitle"),
            ("placeholderText", "setPlaceholderText"),
            ("text", "setText"),
            ("prefix", "setPrefix"),
        ):
            if widget.property("i18n_skip") and getter in ("text", "prefix"):
                continue
            if hasattr(widget, getter) and hasattr(widget, setter):
                value = getattr(widget, getter)()
                if isinstance(value, str):
                    getattr(widget, setter)(localize(value))
        if isinstance(widget, QTabWidget):
            for index in range(widget.count()):
                widget.setTabText(index, localize(widget.tabText(index)))
        if isinstance(widget, QComboBox):
            for index in range(widget.count()):
                widget.setItemText(index, localize(widget.itemText(index)))
        if isinstance(widget, QListWidget):
            for index in range(widget.count()):
                item = widget.item(index)
                item.setText(localize(item.text()))
        if isinstance(widget, QPlainTextEdit):
            widget.setPlainText(localize(widget.toPlainText()))
        widget.update()
