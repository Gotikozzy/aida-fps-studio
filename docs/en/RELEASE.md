# Release procedure

1. Review license/asset provenance, dependencies, security and bilingual documentation.
2. Merge reviewed source and create a protected version tag matching pyproject and __version__.
3. Run ci.yml and the manual windows-candidate workflow from that commit on GitHub-hosted runners.
4. Inspect logs, measurement integrity, native composition, corresponding sources and frozen tests.
5. Complete SignPath onboarding and the signed pilot described in ../../CODE_SIGNING.md.
6. Sign owned inner files, package/sign NSIS uninstaller, then sign the outer installer.
   The provided sign-installer workflow covers only the last stage and does not publish.
7. Verify Authenticode chains, timestamps, publisher policy and signatures of installed files.
8. Test CPU launch, optional GPU, 0.8.14 upgrade, project opening, export and uninstall.
9. Run finalize_artifacts.py on final bytes. Create reviewed dependency/SBOM inventory and
   record commit, workflow run, tool versions, signing request and final hashes.
10. Publish immutable release assets; mirror identical bytes to the official site; publish
    update.json last. Do not replace a published version's installer in place.

Protect source branches/tags and release environments. MFA and human signing approval
are mandatory project policies. Pin workflow actions to reviewed commit SHAs. Fork PRs
must not receive signing/publication secrets. Failed checks stop publication; candidate
hashes are not the hashes of a later signed file.

The release and foundation application are manual external steps; no token, repository URL
or approved identity is fabricated here. Complete ../SIGNPATH_READINESS.md first.

[Other language / Outro idioma](../pt-BR/RELEASE.md)
