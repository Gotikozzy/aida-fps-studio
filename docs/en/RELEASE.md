# Windows release procedure

The release ships without project Authenticode signing. The build and publication
requirements are defined below and in the [distribution policy](../../CODE_SIGNING.md).

1. Review dependency and asset provenance, licenses, security and bilingual documentation.
   Match `pyproject.toml`, `src/dg_fps/__init__.py` and the intended version tag.
2. Commit reviewed changes. Source packaging archives Git `HEAD`, not uncommitted files.
   Run [source checks](../../.github/workflows/ci.yml) and the manual
   [Windows candidate build](../../.github/workflows/windows-candidate.yml) from that commit.
3. Inspect test results, measurement integrity, rebuilt media runtime, native inventory,
   corresponding sources, notices and the frozen CPU self-test. Record the workflow URL,
   commit, tool versions and logs. Run supported GPU validation separately on compatible hardware.
4. Verify installation, CPU startup, project opening, analysis, export, reinstall,
   supported legacy upgrades and uninstall. Use the isolated
   [installer pilot](../INSTALLER_PILOT.md) for system-changing tests.
5. Confirm the project installer/application signing status matches the unsigned policy.
   Preserve upstream signatures. Signing-service enrollment and certificates are not release gates.
6. Run `python scripts/finalize_artifacts.py` on the final installer. Check EXE and ZIP
   hashes, archive contents, file version and the size/digest in `update.candidate.json`.
   These outputs are under `dist/installer/public/`; the source archive is under `dist/`.
7. Generate or review the dependency/SBOM inventory against the exact final installer.
   The [recorded SBOM](../RELEASE_SBOM.md) and its generator are pinned to a historical
   candidate hash; a rebuilt installer requires a newly verified inventory and generator review.
8. Approve the artifacts for publication. Publish immutable versioned assets and
   checksums in the repository release. Mirror identical installer/ZIP bytes to the
   official site. Validate availability and hashes, then publish `update.json` last.
   See [hosting and updater constraints](UPDATES.md).

Never replace a published version's installer in place. Rebuilding the same sources
can change bytes; record fresh hashes and evidence. The earlier 0.8.15 candidate's
[validation record](../GITHUB_BUILD_VALIDATION.md) does not validate a later rebuild.

Protect branches/tags, workflow changes and publication credentials; use MFA for
maintainers and require human release review. Fork PRs receive no publication secrets.
The candidate workflow uploads review artifacts and does not publish a release or
change the live site. Failure of a required check stops publication.

[Português](../pt-BR/RELEASE.md)
