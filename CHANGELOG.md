# Changelog / Histórico

## Unreleased / Não publicado

- Windows distribution uses unsigned project executables and installers; external signing
  workflow, configuration and enrollment checklist removed (ADR 0003).
- Expanded EN/PT entry documentation with operation, requirements, measurement limits,
  project/export behavior and checksum verification; release and updater guidance aligned.
- Distribuição Windows sem assinatura do projeto; integração externa removida. Documentação
  de entrada ampliada em PT/EN e procedimentos de release/atualização alinhados.

## 0.8.15 — 2026-11-15

- Standalone AIDA FPS Studio source repository; other DG modules excluded.
- Apache-2.0 for owned code; original upstream licenses retained.
- English/Portuguese documentation, contribution/security/privacy policies and CI.
- Verified-input build bootstrap; explicit candidate/signing separation.
- Legal UI corrected to open source; optional offline update-check marker.
- Measurement source hashes preserved against the 0.8.14 import baseline.
- Existing site-based updater retained; Authenticode enforcement is not added here.
- Initial signing preparation was later superseded by the unsigned distribution policy.

Repositório independente, licença aberta para código próprio, documentação PT/EN,
políticas e CI. Entradas de build verificadas; candidatura separada de assinatura.
Textos legais e opção offline ajustados. Medição preservada; atualizador mantém o
site atual e ainda não exige Authenticode. A preparação inicial de assinatura foi substituída pela política sem assinatura.

Previous AIDA references / Referências anteriores: docs/releases and docs/reference.
Historical licensing statements apply to historical packages, not this new source release.
