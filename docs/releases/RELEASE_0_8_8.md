# AIDA FPS Studio 0.8.8 — atualização com download confirmado

Ao abrir, o Studio consulta o manifesto oficial sem reutilizar cache. Site
indisponível e versões iguais ou anteriores são ignorados. Uma versão nova
abre uma pergunta em português ou inglês. Após confirmação, o aplicativo baixa
o ZIP, verifica SHA-256 e tamanho, prepara o instalador e utiliza o fluxo de
salvamento existente antes de fechar. Cancelar o salvamento mantém o aplicativo
aberto. O instalador aguarda o processo anterior terminar e continua interativo.

A consulta manual em Sobre também permite iniciar a atualização. A oferta
automática aguarda o término de operações e diálogos ativos. Os termos explicam
o download autorizado; os algoritmos e parâmetros de análise foram preservados.

Validação:

- 316 testes passaram; Ruff sem erros.
- Consulta HTTPS real ao manifesto oficial passou.
- Download com hash, manifesto antigo com SHA separado, cancelamento, pacote
  inválido, extração restrita, consentimento e salvamento cancelado testados.
- Instalador isolado comprovou espera pelo processo anterior.
- Pacote completo passou em instalação nova, atualização, reinstalação,
  conferência dos arquivos, bloqueio por arquivos em uso, downgrade, atalhos,
  preservação de projeto e desinstalação.
- Setup público extraído: 553 arquivos conferidos por hash, 140 arquivos nativos
  aprovados pela revisão existente e self-test do executável aprovado.
- Site local: landing e manifesto 200, download parcial 206, hash e tamanho
  corretos; verificações de idiomas e preferências passaram.

Evidências em `build/tests-088.log`, `build/validate-installer-088.log`,
`build/full-installer-088-recheck.log` e
`build/installer-088-public-proof/validation.json`.
A primeira validação completa coincidiu com a geração do inventário de licenças
pelo empacotamento e deixou esse arquivo fora da lista de remoção do teste.
A repetição com o pacote estabilizado passou; o setup público inclui esse arquivo
na sua lista de remoção.

ZIP: `dist/installer/public/AIDA-FPS-Studio-0.8.8-windows-x64-setup.zip`.
Tamanho: 230.515.676 bytes. SHA-256:
`adeaf49e7feae5c76e018540c60492f5bccf7dac080b9bdb7d6e7ae7f049c931`.

ZIP e SHA copiados para `E:/dg_apps/site_course/static/aida/`; manifesto local
ativado para 0.8.8. Publicação remota será feita pelo usuário. Publicar também
`routers/aida.py`, `templates/aida/home.html`, `static/aida/aida-i18n.js` e
`aida-release.json`. Não há alteração necessária no Nginx existente.

A 0.8.8 precisa ser instalada manualmente uma vez em instalações anteriores:
o download automático passa a existir nesta versão. Atualizações continuam
sujeitas ao aceite do usuário e à execução normal do instalador do Windows.
