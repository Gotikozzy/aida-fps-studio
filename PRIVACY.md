# Privacy / Privacidade

Updated / Atualizado: 2026-11-15. Project owner / responsável pelo projeto: Detonando Gueek
([Gotikozzy](https://github.com/Gotikozzy)); contact / contato: https://detonandogueek.com.br/aida.
Operational hosting statements below were supplied by the site operator; they are not an independent audit.
As informações operacionais abaixo foram fornecidas pelo responsável pelo site, sem auditoria independente.

## Application / Aplicativo

EN: Decoding, indexing, analysis, thumbnails and export run locally. The application does
not upload videos, frames, projects or measurement results, and does not require an account
or a registration form to use/download it. On startup it requests
https://detonandogueek.com.br/aida/update.json. The server receives ordinary HTTP connection
metadata, such as IP and time. A requested download also produces an HTTP request.
The application's direct manifest/ZIP requests do not execute the website's JavaScript
or embed Google Analytics. User-initiated help/site links open the browser and are subject
to the website's analytics/privacy behavior described below.

Disable automatic checks by selecting the optional offline installer component or create
an empty `.disable-update-check` beside the installed EXE (source checkout: repository
root). Delete it to re-enable. Analysis works offline. Downloads and installer launch
require confirmation. Local logs rotate and may contain paths; inspect diagnostics before
sharing. Data/settings use platformdirs under the current Windows profile. Uninstall
preserves projects, settings/cache and unrecognized user files; the offline marker may remain.

PT: Decodificação, indexação, análise, miniaturas e exportação são locais. O aplicativo
não envia vídeos, frames, projetos ou medições e não exige conta nem formulário cadastral
para uso/download. Na abertura consulta o manifesto acima; o servidor recebe metadados
HTTP usuais, como IP e horário. Downloads também geram requisições HTTP. As consultas
diretas do aplicativo não executam JavaScript do site nem incorporam Google Analytics.
Links de ajuda/site abertos pelo usuário usam o navegador e seguem a política do site.

Desative consultas pelo componente offline do instalador ou crie `.disable-update-check`
ao lado do EXE (nos fontes: raiz do repositório). Apague-o para reativar. A análise funciona
offline. Download e execução do instalador exigem confirmação. Logs rotativos locais
podem conter caminhos; revise diagnósticos. Dados usam platformdirs no perfil Windows.
Desinstalar preserva projetos, preferências, cache e arquivos desconhecidos do usuário;
o marcador offline pode permanecer.

## Website, hosting and access logs / Site, hospedagem e logs de acesso

EN: The official site is hosted on a VPS at **Hostinger** and uses **Nginx access logs**.
The operator reports monthly retention for these server access logs. Depending on the
configured Nginx format, records can include IP, time, requested URL, status and client
metadata. The operator does not maintain a separate downloader registration/history or
request registration details. This does not mean an installer/manifest request is absent
from the normal Nginx access log. The exact Nginx log format has not been independently checked.

PT: O site oficial usa VPS na **Hostinger** e **logs de acesso Nginx**. O responsável
informou retenção mensal desses logs. Conforme o formato configurado, podem conter IP,
horário, URL solicitada, status e metadados do cliente. Não há cadastro nem histórico
específico mantido de quem baixou o programa. Uma requisição de manifesto/instalador pode
constar no log normal de acesso; o formato exato do Nginx não foi auditado nesta preparação.

Hosting provider / Provedor: [Hostinger privacy policy](https://www.hostinger.com/legal/privacy-policy).
Nginx format reference / Formato: https://nginx.org/en/docs/http/ngx_http_log_module.html.

## Website analytics / Analytics do site

EN: Website pages use **Google Analytics**, as reported by the operator. Use and retention
follow the property's actual settings and applicable Google policies. The operator confirmed a **2-month user/event-data retention setting** on 2026-11-15.
Google provides configurable retention controls; aggregated reports can have different
retention behavior. This is separate from the VPS's monthly Nginx access-log retention.
No Google Analytics SDK is part of the desktop application.

PT: As páginas do site usam **Google Analytics**, conforme informado. O tratamento e a
retenção seguem a configuração efetiva da propriedade e as políticas aplicáveis do Google.
O responsável confirmou retenção de **2 meses para dados de usuários/eventos** em
2026-11-15. Relatórios agregados podem ter tratamento diferente segundo as regras do Google. Esse prazo é separado da
retenção mensal dos logs Nginx. O aplicativo desktop não inclui SDK Google Analytics.

[Google partner-site information / Informações sobre sites parceiros](https://policies.google.com/technologies/partner-sites?hl=pt-BR).
[Google retention controls / Controles de retenção](https://support.google.com/analytics/answer/7667196?hl=pt-BR).

## Backups / Cópias de segurança

EN: The operator reports weekly snapshots, daily database backups and encryption at rest.
The retention/expiry of backup copies has not been supplied. Those intervals describe
backup frequency, not a confirmed deletion deadline for every copy of access data.

PT: O responsável informou snapshots semanais, backups diários de banco e criptografia
em repouso. Os prazos de retenção/expiração das cópias não foram informados. As frequências
de backup não equivalem a um prazo confirmado de exclusão de todas as cópias de dados.

## Requests / Solicitações

Use the official contact channel on https://detonandogueek.com.br/aida for questions about
site records or privacy. GitHub and Google/Hostinger services also apply their own policies.
Consulte o contato oficial para questões sobre registros do site/privacidade. GitHub,
Google e Hostinger também aplicam suas políticas aos respectivos serviços.
