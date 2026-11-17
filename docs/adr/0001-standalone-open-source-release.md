# ADR 0001 — Standalone open-source distribution / distribuição aberta

Date: 2026-11-15. Status: accepted for local preparation.

Context: 0.8.14 was a validated proprietary distribution inside a larger private
workspace. The owner authorized publishing only AIDA FPS Studio under the proposed
Apache-2.0 model, in a separate 0.8.15 folder. Other analyzer modules are excluded.

Decision: establish a standalone repository and normative SPECIFICATION.md;
license owned code Apache-2.0, retain upstream notices, preserve measurement
sources byte for byte. Change only version, legal UI, packaging and an offline
update-check switch. Build from verified upstream inputs, keep generated binaries
out of Git, and prepare CI with a separately gated signing integration. The signing
portion of this decision is superseded by [ADR 0003](0003-unsigned-windows-distribution.md).

Consequences: build tools and external accounts still need configuration; release
approval is separate from successful tests. No other modules, private footage or
parent-repository history are imported. Historical AIDA documents are references,
not current licensing authority. New documentation is maintained in PT and EN.

Contexto: a 0.8.14 era uma distribuição validada dentro de um workspace maior.
O titular autorizou abrir somente o AIDA em uma pasta 0.8.15 separada, seguindo
a proposta Apache-2.0. Outros módulos estão excluídos.

Decisão: repositório independente, SPECIFICATION.md normativa, preservação das
licenças upstream e dos fontes de medição. Mudanças limitadas à versão, textos
legais, empacotamento e opção offline de atualização. Binários gerados fora do
Git; build com entradas verificadas e integração de assinatura condicionada à configuração.
A parte de assinatura foi substituída pela [ADR 0003](0003-unsigned-windows-distribution.md).
