# AIDA FPS Studio 0.8.6 — fechamento de distribuição e usabilidade

## Composição de mídia

O runtime anterior do wheel PyAV continha x264/x265 GPL. Ele não é usado no
instalador desta edição. A nova composição foi compilada de fontes upstream
não modificados: FFmpeg 8.0.1 LGPL-3.0-or-later, OpenH264 2.6.0 BSD, dav1d
1.5.1 BSD e nv-codec-headers 12.1.14.0 MIT, com GPL/nonfree desabilitados.
PyAV 16.1.0 BSD foi religado somente pelos nomes de DLL importados. A exportação
CPU usa OpenH264; NVIDIA NVENC e Optical Flow continuam opcionais.

Os algoritmos, limiares e gráficos da análise não foram alterados. O único
ajuste na apresentação foi a seleção/configuração do encoder CPU. Foram
comparados quatro trechos reais de 120 frames (GTA, Starfield, Gears e GTA 4K):
pixels, precisão de sinal, timestamps e medições CPU/NVIDIA idênticos à base.
A comparação ignora apenas UUIDs de identificação gerados a cada execução.
Isso comprova os casos testados; não equivale a testar todos os vídeos possíveis.

Evidência: `build/lgpl-native/comparison.json`, com os documentos completos
baseline/candidato em `build/lgpl-runtime/baseline.json` e
`build/lgpl-native/candidate.json`.

## Licenças e aceite

- Termos bilíngues para software gratuito de código próprio fechado.
- Aceite explícito no instalador, com os termos e textos completos dos avisos
  e licenças de terceiros, preservando seus direitos.
- Consulta em Ajuda > Termos e licenças, com busca e fechamento por teclado.
- Fontes LGPL completos e instruções incluídos na instalação, sem depender de
  um futuro download no site. Eles não contêm o código próprio de análise.
- Wrappers Python LGPL do Qt/PySide/Shiboken em arquivos substituíveis, além das DLLs.
- Removidos o plugin FFmpeg do OpenCV e o driver OpenGL de software, não usados
  pelo Studio. OpenCV continua responsável pelo processamento de imagens/fluxo.
- Revisão técnica dos 140 arquivos nativos por versão, hash, avisos e fontes.
  Inventário dos pacotes Python também vinculado à revisão. A geração pública
  recusa composição alterada, arquivos sem revisão ou codecs GPL conhecidos.

Os termos originais de terceiros, incluindo suas condições e ressalvas, continuam
aplicáveis. A revisão técnica de distribuição não é uma garantia jurídica universal
nem substitui as condições dos titulares.

Referências primárias: [Qt LGPL](https://www.qt.io/development/open-source-lgpl-obligations),
[FFmpeg](https://ffmpeg.org/legal.html),
[OpenH264](https://github.com/cisco/openh264),
[Microsoft redistributables](https://learn.microsoft.com/cpp/windows/redistributing-visual-cpp-files).

## Instalação e atualização

O instalador apresenta instalação nova, atualização ou reinstalação conforme a
versão detectada. Impede downgrade e instalação/desinstalação com os arquivos
do aplicativo em uso. Projetos, preferências e cache ficam fora da instalação.

Arquivos obsoletos são removidos por uma lista de caminhos gerenciados. A
comparação respeita a insensibilidade a maiúsculas/minúsculas do Windows. Esse
problema foi encontrado e corrigido durante o teste completo de atualização.
Não há exclusão recursiva da pasta de instalação nem de projetos pessoais.

O ciclo foi executado com o script NSIS de produção e os payloads completos
0.8.5/0.8.6, usando identidade e associação isoladas. Incluiu instalação nova,
upgrade, conferência dos hashes instalados, remoção de bibliotecas aposentadas,
reinstalação, arquivo em uso, downgrade, atalhos, associação, nova instalação
limpa da versão atual e desinstalação. O projeto de teste foi preservado.
Os setups de ensaio dispensam compressão; o instalador final comprimido é
conferido separadamente por extração e hashes. A instalação real do usuário
não foi substituída ou removida.

Evidência: `build/AIDA Installer Test 9d1bc74a0abb/validation.json` e
`build/full-installer-086-final.log`.

## Usabilidade e exportação

299 testes passaram com o novo runtime. Ruff sem erros. Os fluxos testados
incluem importação cancelada, troca de projeto, projeto inválido, retorno ao
Início sem perder trechos, atalhos I/O/Delete, cancelamento, validação de nome,
escolha de pasta cancelada, salvamento, restauração das opções, exportação,
falha de gravação, idiomas e leitura/busca de licenças. A disposição do diálogo
de licenças foi ajustada após inspeção visual.

O executável congelado passou pelo self-test após instalação nova e atualização.
Exportações completas por CPU e NVIDIA preservaram 16/16 frames, taxa de 30 FPS
e primárias/transferência/matriz BT.709. Evidências em
`build/encoder-proof-086/validation.json`, `build/selftest-086-lgpl/` e
`build/tests-086-final-native.log`.

A inspeção nativa cobriu Início e seletor Windows; os demais caminhos foram
exercitados por automação Qt. Ainda não houve teste com usuários externos ou
validação em uma segunda máquina Windows limpa. O piloto deve cobrir isso.

O ZIP final é do instalador, não do ambiente de desenvolvimento. A publicação
no servidor e o anúncio de atualização não foram realizados nesta etapa.

## Conferência final do pacote

ZIP: `dist/installer/public/AIDA-FPS-Studio-0.8.6-windows-x64-setup.zip`.
Tamanho: 230.615.998 bytes. SHA-256:
`e260cdef77088f55b3f9a021c69312c70d5ccacdf2598f8df5aaa3e87f2276c7`.

O instalador final comprimido foi extraído e seus 550 arquivos foram comparados
por hash com a distribuição compilada. Os 140 nativos passaram pela revisão,
os fontes e avisos esperados estavam presentes e o texto de aceite correspondia
ao conjunto completo. Não havia DLL x264/x265. O executável extraído também
passou pelo self-test. Evidência em `build/installer-086-public-proof/validation.json`.
