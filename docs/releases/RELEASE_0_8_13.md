# AIDA FPS Studio 0.8.13 — desempenho com medição preservada

Pipeline CPU com antecipação limitada para leitura de quadros originais e
composição de exportação. Encode/mux continuam no job serial de GPU. Não altera
codec, presets, resolução analítica, limiares nem runtime PyAV/FFmpeg.

O mapa visual reutiliza o preparo do quadro anterior. A entrega QImage → PyAV
dispensa uma cópia RGB intermediária. O leitor de exportação usa decode CPU
multithread quando elegível e retoma estritamente após falha, sem aceitar
quadros ausentes. Cancelamento e falhas encerram os produtores antes do retorno.

O adaptador NVIDIA 1.2.1 reutiliza conversões cinza com comparação integral dos
pixels e invalidação de arrays mutáveis. Os vetores, preset SLOW, interpolação,
chamadas bidirecionais e DLL permanecem preservados. O cache temporal converte
colunas em lote e compartilha strings repetidas; sua identidade e formato são
os mesmos. A primeira indexação continua decodificando o vídeo completo.

Relatórios reutilizam inferências automáticas da sessão, mantendo os overrides
manuais separados. Não há migração de projetos nem alteração de schema.

Validação: 387 testes passaram com o runtime LGPL próprio. Os 18 arquivos
protegidos, incluindo analisadores, backend CPU, encoder, verificação de MP4 e
DLL NVIDIA, mantiveram hashes idênticos à 0.8.12. Os módulos protegidos também
foram comparados diretamente entre os executáveis compilados.

O teste NVIDIA real passou em três dimensões, incluindo entradas mutáveis,
views não contíguas, resultados retidos e troca de thread. O autoteste do
executável confirmou análise CPU, 16 frames H.264, cadência sintética de 15 FPS,
interface PT/EN e disponibilidade de Optical Flow/NVENC na RTX 2080 SUPER.

Evidências em `build/tests-0813.xml`, `build/tests-0813.log`,
`build/v0813-proof/measurement-integrity.json`,
`build/v0813-proof/native-cache.json` e `build/self-test-0813/self-test.json`.
Uma checagem adicional comparou os 288 quadros RGB originais, PTS e metadados
entre leitura convencional e multithread nos quatro vídeos reais, antes de
qualquer overlay ou redução: `build/v0813-proof/threaded-decode.json`.

O roteiro NSIS de produção passou com payload real e identidade isolada:
instalação inicial, upgrade, reinstalação, hashes de todos os arquivos,
remoção de arquivos aposentados, bloqueio de aplicação em uso e downgrade,
atalhos/associação isolada, preservação de projeto e desinstalação.
Registro em `build/full-installer-0813.log`; instalação existente preservada.

## Comparação real com a 0.8.12

Quatro trechos de 72 quadros originais, três repetições por backend/codificador,
medianas na mesma máquina (Ryzen 7 3800XT, RTX 2080 SUPER), com o mesmo runtime
LGPL. Os tempos de análise incluem relatórios; os de exportação incluem captura
de hashes dos quadros compostos para verificação. Não são um benchmark universal
nem estimativa para vídeos inteiros.

| Fonte | Exportação CPU: antes → depois | Redução | NVENC: antes → depois | Redução |
| --- | --- | --- | --- | --- |
| GTA VI | 3,88 → 1,77 s | 54,3% | 3,55 → 2,13 s | 40,0% |
| Starfield | 4,81 → 2,20 s | 54,2% | 4,36 → 2,57 s | 41,1% |
| Gears E-Day | 7,74 → 3,09 s | 60,1% | 7,29 → 3,55 s | 51,3% |
| GTA VI 4K | 9,18 → 3,33 s | 63,7% | 8,96 → 3,60 s | 59,8% |

As variações observadas na análise foram pequenas: redução de 1,3–4,1% em CPU
e 3,3–4,8% em NVIDIA. Ganhos desta ordem precisam de amostras maiores para serem
generalizados. A leitura do cache temporal caiu 29,8–36,1%, de aproximadamente
219–295 ms para 143–207 ms. Isso acelera reaberturas; a primeira indexação não
foi alterada. Em trechos curtos, o custo de inicialização/teste do NVENC pode
superar sua vantagem de codificação; os percentuais comparam cada modo consigo.

Todos os quatro casos preservaram o índice completo, pixels/PTS de entrada,
resultados completos de medição por backend, pixels de composição, pixels/PTS
do H.264 decodificado e mapeamento de proveniência. A comparação exclui UUIDs
gerados, IDs aninhados redundantes (ID/versão do analisador no nível principal
continuam comparados), localização da DLL e versão declarada 1.2.0/1.2.1 do
adaptador, inclusive dentro das ROIs. Políticas, limiares, métricas, evidências,
eventos, lacunas e resumos continuam comparados sem tolerância numérica.

Dados originais preservados em `build/v0813-proof/before.json`; resultados,
comparação final e exclusões em `build/v0813-proof/after/result.json`.
A rechecagem dos documentos salvos pode ser executada com
`validate_pipeline_performance.py --compare-only --baseline
build/v0813-proof/before.json --output build/v0813-proof/after/result.json`.

## Entrega

Executável: `dist/0.8.13/AIDA-FPS-Studio/AIDA-FPS-Studio.exe`.
Instalador: `dist/installer/public/AIDA-FPS-Studio-0.8.13-windows-x64-setup.exe`
(230534167 bytes). SHA-256:
`cfc8d04ac3cb7834ba235be4919a0e560877d52ca5f5d3185f8d879f0b0423fd`.

ZIP público: `AIDA-FPS-Studio-0.8.13-windows-x64-setup.zip` (230534353 bytes).
SHA-256: `53b3321ff6eb9e77258cd578e1207b4f43c3cd93c7b27923f6e3a2ffe129d46e`.
CRC do ZIP e checksums conferidos; `build/v0813-proof/delivery.json` registra
a entrega. Pacotes gerados localmente; manifesto remoto não publicado.
