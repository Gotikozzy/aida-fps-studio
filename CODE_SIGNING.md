# Code signing policy

[Privacy / Privacidade](PRIVACY.md) · [Release EN](docs/en/RELEASE.md) · [Release PT](docs/pt-BR/RELEASE.md)

## Status / Situação

EN: Prepared for application, **not enrolled, approved or signed by SignPath Foundation**.
Local binaries and source archives must not be described as Foundation-signed. The signing
workflow is gated by repository configuration and does not publish releases. Foundation
approval, verifiable reputation and technical onboarding are external requirements.
PT: Preparado para candidatura; **sem adesão, aprovação ou assinatura pela Foundation**.
Não anuncie aprovação em binários ou fontes locais. O workflow é condicionado à
configuração e não publica releases. Aprovação e onboarding são requisitos externos.

## Responsibility / Responsabilidade

Project owner / titular: Detonando Gueek. Initial author and reviewer: project owner.
Production signing approver: project owner, subject to onboarding verification.
Actual GitHub accounts and SignPath identities must be recorded in the repository's
settings and this policy before enabling signing; they are not invented in this package.
External PRs require review. Every production signing request requires a trusted person's
manual approval. All team members use MFA on GitHub and SignPath. Restrict signing to
reviewed source branches/tags and GitHub-hosted builds. Protect workflow changes and
release publication; fork PRs never receive signing secrets.

Titular e autor/revisor inicial: Detonando Gueek. Aprovador de produção: titular,
sujeito à verificação no onboarding. Registrar contas reais antes de habilitar assinatura.
PRs externos exigem revisão; cada solicitação de produção exige aprovação humana.
Equipe com MFA no GitHub/SignPath. Restringir branches/tags, runners e publicação.

## Scope / Escopo

Sign only owned AIDA executable, owned bridge and installer/uninstaller after review.
Do not apply wildcard signing to Qt, FFmpeg, Python, PyAV, NumPy or other upstream
binaries. Preserve their signatures and license/replacement rights. Project metadata
must identify AIDA FPS Studio and the same version across its signed files.
Build, sign inner application files, package, sign uninstaller/installer, verify signatures,
then compute ZIP hashes. Installer-only signing does not sign installed programs.

Assinar apenas arquivos próprios aprovados. Preservar assinaturas e licenças upstream.
Metadados do produto e versão consistentes. Assinar arquivos internos antes de empacotar;
instalador assinado sozinho não assina o aplicativo instalado.

## Enablement gate / Critérios para habilitar

Follow docs/SIGNPATH_READINESS.md. Configure project/organization identifiers and token,
artifact rules, branch constraints, identities, MFA and manual production approval.
Run a complete signed pilot including NSIS uninstaller handling. The supplied workflow
submits a final installer for signing; it does not implement inner-file/uninstaller signing.
Those stages remain explicit prerequisites to a fully signed production distribution.
Do not enable production publication until that pilot and the listed checks pass.

Siga o checklist. O workflow fornecido assina o instalador final; assinatura dos arquivos
internos e do desinstalador exige integração adicional e piloto. Não publicar como
pacote completamente assinado enquanto essas etapas não estiverem verificadas.

After actual acceptance, add the official attribution on home/download/release pages:
“Free code signing provided by SignPath.io, certificate by SignPath Foundation”.
Add it only when accurate. Rules: https://signpath.org/terms
Integration: https://docs.signpath.io/trusted-build-systems/github
