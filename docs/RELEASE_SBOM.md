# Candidate SBOM / SBOM do candidato

[Inventory / Inventário](validation/AIDA-FPS-Studio-0.8.15.cdx.json) uses CycloneDX 1.5
and passed the upstream JSON schema. It describes the exact unsigned installer
SHA-256 `330f08d0daf617804ea145d0d0594a19d19b16868f6dd6bc54c826d9319585b0`.

Coverage: 565 extracted NSIS files, 11 package metadata records and the outer EXE
(577 components). Conditional/offline files and NSIS helpers are included even
when a default installation does not install them. The 138 native review records
were checked against approved hashes and corresponding notice hashes. A deliberately
invalid native approval was rejected. License names are inherited from the existing
review; files without a supported license mapping do not receive an invented one.

Cobertura: 565 arquivos extraídos, 11 registros de pacotes e o EXE externo (577
componentes). Inclui arquivos condicionais e auxiliares NSIS. Os 138 registros
nativos e hashes dos avisos foram conferidos; aprovação adulterada foi recusada.
Licenças vêm da revisão existente, sem atribuições inventadas. O schema oficial
CycloneDX 1.5 passou.

This is a file/package inventory, not a complete transitive dependency graph,
independent legal clearance or Foundation acceptance. Microsoft system-library
acceptance remains pending. A signed release has different hashes and needs a
new inventory. The earlier Python wheel BOM covers build inputs separately.

Este inventário não é grafo transitivo completo nem aceite jurídico/da Foundation.
O enquadramento das bibliotecas Microsoft continua pendente. A release assinada
precisará de novo inventário/hashes. O SBOM anterior de wheels cobre entradas de build.

Reproduce from a fresh 7-Zip extraction (not a directory used to launch the app):
Reproduzir a partir de extração limpa pelo 7-Zip:

```powershell
python scripts/generate_release_sbom.py <extracted-payload> <build-evidence/installer/distribution-review.json> <verified-unsigned-installer.exe> <output.cdx.json>
```

The generator is restricted to this candidate hash and does not change binaries.
O gerador é restrito ao hash deste candidato e não altera os binários.
