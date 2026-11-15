# ADR 0002 — Isolated installer pilot / piloto isolado

Date: 2026-11-15. Status: accepted for validation tooling.

The local machine has Sandbox disabled and this session cannot administer Hyper-V.
Use a disposable GitHub-hosted Windows runner for exact-installer integration tests.
Never install/uninstall the production identity on the developer's working profile.
Require a GitHub Actions environment marker and explicit pilot consent in the harness.

Use the original 0.8.14 installer as an immutable legacy input (SHA-256 pinned),
temporarily stored in a draft release accessible to repository users with push access.
This input does not claim a source-rebuilt or re-licensed historical binary. Fetch
the 0.8.15 installer from the successful, hash-pinned GitHub workflow artifact.
All installed applications and HKCU associations are confined to the disposable runner.
Use the real product identity there to test actual registration and removal behavior.
The manual pilot workflow uses contents:write only to read the private draft input;
it never creates/publishes releases or enables signing. Fork PRs cannot trigger it.

Check fresh install, silent upgrade, reinstall, downgrade refusal, locked-file refusal,
parent-process update gating, payload hashes, project/report preservation, CPU export,
normal frozen project opening, associations/shortcuts and uninstall. Record what was
actually executed. GPU checks run separately and serially on compatible local hardware.
Do not modify application/measurement code to add a special pilot execution path.

O piloto usa runner Windows descartável porque o Sandbox local está desativado e
a sessão não pode administrar VMs. Instaladores originais são verificados por hash;
a referência 0.8.14 fica em rascunho de release, sem publicação. Registro HKCU e
associações reais são testados somente no runner. O workflow é manual, sem assinatura,
sem publicação e sem execução por PR de fork. Testes GPU são locais e serializados.
Não se cria caminho especial de QA dentro do núcleo do aplicativo.
