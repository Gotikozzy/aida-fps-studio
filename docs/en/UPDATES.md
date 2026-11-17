# Updates and hosting

The current site remains https://detonandogueek.com.br/aida/update.json. The updater
constructs versioned ZIP URLs under the same official domain and uses same-origin
redirect rules. GitHub release asset redirects are not a drop-in replacement.

Expected manifest: `{"version":"0.8.15","sha256":"<64 hex characters>","size":123}`.
Use the actual final ZIP size and digest. Versions use three decimal components.
The ZIP contains exactly `AIDA-FPS-Studio-<version>-windows-x64-setup.exe`.
The app limits manifest/package sizes, checks SHA-256, rejects unexpected archive entries,
requires confirmation and validates PE structure before launch. It does **not** enforce
Authenticode. That improvement needs a separate reviewed updater change and certificate
rotation policy. Do not pin a short-lived leaf certificate forever.

Release order: reviewed unsigned CI artifact -> GitHub Release -> identical site mirror -> manifest.
Keep existing URL/name conventions for already installed clients. Compute the EXE digest
from the final installer and the ZIP digest after packaging that exact EXE. SHA-256 from the same
origin does not protect against compromise of that origin. A signed manifest/TUF-style
scheme may be evaluated later; it is not present in this version.
Offline checks are controlled by the marker described in ../../PRIVACY.md.

[Other language / Outro idioma](../pt-BR/UPDATES.md)
