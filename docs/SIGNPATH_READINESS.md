# SignPath readiness / Preparação para SignPath

This is a release gate, not an approval claim. Checked items are local preparation only.
Este checklist não declara aprovação. Itens preparados referem-se apenas ao pacote local.

- [x] Owned code licensed Apache-2.0; original third-party notices retained.
- [x] Standalone scope; no other DG analyzer modules or private media datasets.
- [x] PT/EN user, developer, methodology, build and release documentation.
- [x] Version 0.8.15; measurement import baseline and synthetic regression tests.
- [x] GitHub-hosted CI and manually gated installer submission workflow prepared.
- [x] Privacy disclosure and optional offline update-check mode.
- [x] Publish the real repository URL and GitHub owner mapping (Gotikozzy).
- [x] Owner confirmed image redistribution rights on 2026-11-15; see docs/ASSETS.md.
- [ ] Confirm system-library exception with SignPath for Microsoft runtime/driver usage.
- [x] Clean GitHub-hosted native build, 411 tests, hashes and technical native inventory (138 files).
- [x] Python build-input and extracted-candidate CycloneDX inventories recorded; see docs/RELEASE_SBOM.md for coverage/limits.
- [x] Downloaded/verified build inputs and staged corresponding sources during the clean build.
- [x] Six native GPU vector/magnitude cases exactly match 0.8.14 on RTX 2080 SUPER.
- [x] Four real-video CPU/GPU windows matched; installer/upgrade/uninstall pilot passed for 0.8.12 and 0.8.14 (see scoped evidence).
- [x] Protect main with PR/CI requirements; enable private security reports.
- [x] Configure signing-production with owner approval; SIGNPATH_ENABLED remains false.
- [x] GitHub owner confirmed MFA enabled on 2026-11-15 (owner declaration).
- [ ] Configure/verify SignPath MFA and identities during onboarding.
- [ ] Publish actual site hosting/log-retention policy and release/download pages.
- [ ] Submit project application; Foundation checks reputation and repository control.
- [ ] Configure organization/project IDs, artifact constraints and manual signing approval.
- [ ] Complete application/bridge/uninstaller signing stages and a signed pilot.
- [ ] Verify installed signatures, upgrade from 0.8.14, uninstall and LGPL replacement.
- [ ] Publish exact signed bytes; calculate hashes afterward; update site manifest last.
- [ ] Add Foundation attribution only after acceptance.

Rules checked 2026-11-15: https://signpath.org/terms
GitHub origin rules: https://docs.signpath.io/trusted-build-systems/github
Do not claim compliance merely because this checklist or workflows exist.
Não declarar conformidade apenas pela existência destes arquivos.

Build evidence / Evidências: [GitHub build validation](GITHUB_BUILD_VALIDATION.md).
