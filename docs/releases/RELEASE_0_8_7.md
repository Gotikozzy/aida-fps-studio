# AIDA FPS Studio 0.8.7 — termos legíveis e acesso às licenças

O instalador apresenta os termos próprios do AIDA no idioma selecionado e um
aviso destacado dos componentes LGPL e de terceiros. O botão Consultar licenças
completas abre um catálogo HTML offline antes do aceite. Os documentos completos,
copyrights, fontes e instruções de substituição continuam no pacote e na instalação.
O aceite não contém mais a concatenação de aproximadamente 1,3 milhão de caracteres.
Os termos apresentados têm 1.861 caracteres em português e 1.650 em inglês.

Ajuda > Termos e licenças abre uma visão geral e permite consultar os termos do
AIDA no idioma da interface, a licença do produto e os documentos por componente.
Sobre AIDA FPS Studio é a última ação do menu Ajuda, após um separador.

Não foram alterados algoritmos, parâmetros, binários de mídia ou resultados da
análise. A versão do produto e os componentes de apresentação/distribuição mudaram.

Validação:

- 301 testes passaram; Ruff sem erros.
- Executável congelado passou pelo self-test, inclusive após extração do setup final.
- Instalação isolada com payload completo: instalação nova, atualização,
  reinstalação, hashes dos arquivos instalados, remoção de obsoletos, bloqueio de
  arquivos em uso e downgrade, atalhos, associação isolada, preservação de projeto
  e desinstalação. A instalação real do usuário não foi substituída.
- Setup final extraído: 553 arquivos conferidos por hash, 140 arquivos nativos
  aprovados pela revisão existente; catálogo e termos antes do aceite conferidos.
- A primeira inspeção visual identificou controles abaixo da área disponível;
  o espaçamento foi corrigido. A revisão visual do ajuste foi interrompida pelo
  Escape físico do usuário. Não se afirma validação visual final do instalador.

Evidências: `build/tests-087.log`, `build/full-installer-087.log`,
`build/installer-087-public-proof/validation.json` e seu diretório `self-test`.

Pacote: `dist/installer/public/AIDA-FPS-Studio-0.8.7-windows-x64-setup.zip`.
Tamanho: 230.498.400 bytes. SHA-256:
`a9f340921f96385b8f82850462c0db87722999f1db9ebcf20ac3fa8a48a68ea6`.

ZIP e SHA-256 copiados para `E:/dg_apps/site_course/static/aida/` e manifesto local
atualizado para 0.8.7, publicado=true. A publicação no servidor é feita pelo usuário.
