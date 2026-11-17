# Windows distribution policy / Política de distribuição Windows

## English

AIDA FPS Studio distributes its Windows application, native bridge and NSIS
installer without project Authenticode signing. No signing service, certificate,
API token or signing environment is required by the build. Preserve any original
upstream signatures; do not apply project signing to third-party binaries.

Windows can display an unknown-publisher or reputation warning. Users should check
origin, version and the published SHA-256 before running a package. Do not instruct
users to disable antivirus or Windows security protections. A matching checksum
establishes agreement with the reference bytes, not publisher identity or safety.

Release review requires a traceable source commit and CI run, passing tests,
measurement-source integrity, native dependency review, license notices,
corresponding sources, installer lifecycle tests and an inventory for the final
artifact. Compute EXE and ZIP hashes after all packaging steps. Publish immutable
assets, mirror identical bytes to the official site and update the manifest last.
[Release procedure](docs/en/RELEASE.md).

The existing updater checks size, SHA-256, ZIP contents and PE structure. It does
not verify Authenticode or a cryptographically signed manifest. HTTPS and control
of the distribution origin remain part of the trust boundary. A checksum obtained
from the same compromised origin would not provide independent authentication.

Keep source branches, workflow edits and publication access protected. Review
external PRs, use MFA for maintainer accounts and withhold publication credentials
from fork builds. Publication is manual and follows artifact review.

Future signing requires a reviewed architecture decision covering publisher
identity, key custody, owned-file scope, installer/uninstaller handling and updater
compatibility. [Current decision](docs/adr/0003-unsigned-windows-distribution.md).

## Português

O AIDA FPS Studio distribui aplicativo Windows, ponte nativa e instalador NSIS sem
assinatura Authenticode do projeto. O build não exige serviço de assinatura,
certificado, token ou ambiente de assinatura. Preserve assinaturas originais de
terceiros; não aplique assinatura do projeto aos binários de dependências.

O Windows pode exibir avisos de editor desconhecido ou reputação. Confira origem,
versão e SHA-256 publicado antes de executar. Não oriente a desativação do antivírus
ou das proteções do Windows. Um checksum igual comprova correspondência com os
bytes de referência, não identidade do editor ou segurança do programa.

A revisão da release exige commit e execução CI rastreáveis, testes aprovados,
integridade dos fontes de medição, revisão nativa, avisos de licenças, fontes
correspondentes, testes do ciclo de instalação e inventário do artefato final.
Calcule hashes do EXE e ZIP depois de todo o empacotamento. Publique arquivos
imutáveis, espelhe os mesmos bytes no site e atualize o manifesto por último.
[Procedimento de release](docs/pt-BR/RELEASE.md).

O atualizador verifica tamanho, SHA-256, conteúdo do ZIP e estrutura PE. Não valida
Authenticode nem manifesto assinado criptograficamente. HTTPS e controle da origem
de distribuição integram a fronteira de confiança. Um hash obtido da mesma origem
comprometida não oferece autenticação independente.

Proteja branches, alterações em workflows e acesso à publicação. Revise PRs
externos, use MFA nas contas mantenedoras e não forneça credenciais de publicação
a builds de forks. A publicação é manual e sucede a revisão dos artefatos.

Uma futura assinatura exige decisão revisada sobre identidade, guarda das chaves,
escopo de arquivos próprios, instalador/desinstalador e compatibilidade do atualizador.
[Decisão vigente](docs/adr/0003-unsigned-windows-distribution.md).
