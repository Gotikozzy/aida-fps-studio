# ADR 0003 — Unsigned Windows distribution / Distribuição Windows sem assinatura

Date / Data: 2026-11-17. Status: accepted / aceita. Supersedes the signing
integration and release gates in ADR 0001; measurement architecture is unchanged.
Substitui a integração e os critérios de assinatura da ADR 0001; preserva a medição.

## Decision / Decisão

Distribute the Windows application and NSIS installer without project Authenticode
signing. Remove the external signing workflow, artifact configuration and enrollment
checklist. The Windows candidate workflow already produces unsigned packages and
remains the build entry point. Publication remains a reviewed, manual operation.

Distribuir o aplicativo Windows e o instalador NSIS sem assinatura Authenticode do
projeto. Remover workflow, configuração de artefatos e checklist do serviço externo.
O workflow de candidato Windows já gera pacotes sem assinatura e permanece como
entrada do build. A publicação continua manual, após revisão.

## Consequences / Consequências

Record source commit, CI run, tests, native inventory, corresponding sources, SBOM
and SHA-256 of final EXE/ZIP bytes. Preserve any upstream signatures. Hashes detect
byte changes relative to a trusted reference; they do not authenticate a publisher.
Document possible Windows reputation warnings without recommending that users
disable security protections. The existing updater checks hashes and PE structure;
it does not verify Authenticode. Keep its URL and manifest format unchanged.

Registrar commit, execução CI, testes, inventário nativo, fontes correspondentes,
SBOM e SHA-256 dos bytes finais do EXE/ZIP. Preservar assinaturas de terceiros.
Hashes detectam alterações frente a uma referência confiável; não autenticam o
editor. Documentar possíveis alertas do Windows sem orientar a desativação das
proteções. O atualizador verifica hash e estrutura PE, sem validar Authenticode;
suas URLs e formato de manifesto permanecem iguais.

Future project signing requires a new reviewed decision and updated release
verification. No analyzer, decoding, timestamp, GPU queue or presentation algorithm
changes are part of this decision.
Uma futura assinatura exige nova decisão e revisão da verificação de release.
Esta decisão não altera algoritmos de análise, mídia ou apresentação.
