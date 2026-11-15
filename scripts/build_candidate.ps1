param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$ProjectRoot = Split-Path $PSScriptRoot -Parent
Push-Location $ProjectRoot
try {
    function Invoke-Python {
        & $Python @args
        if ($LASTEXITCODE -ne 0) { throw "Python command failed: $args" }
    }
    Invoke-Python scripts/verify_source_integrity.py
    Invoke-Python scripts/bootstrap_sources.py --extract
    # Extract the verified self-extracting toolchain as data, never run its EXE.
    $SevenZip = (Get-Command 7z.exe -ErrorAction Stop).Source
    & $SevenZip x build/lgpl-native/w64devkit-x64-2.11.0.7z.exe '-obuild/lgpl-native/toolchain' -y
    if ($LASTEXITCODE -ne 0) { throw 'Toolchain extraction failed' }
    Invoke-Python scripts/build_lgpl_ffmpeg.py
    Invoke-Python scripts/prepare_lgpl_runtime.py build/lgpl-native/prefix/bin build/lgpl-native/site
    Invoke-Python scripts/build_nvidia.py
    $PreviousPythonPath = $env:PYTHONPATH
    try {
        $env:PYTHONPATH = "$ProjectRoot/build/lgpl-native/site;$ProjectRoot/src"
        Invoke-Python -m pytest -q
    } finally { $env:PYTHONPATH = $PreviousPythonPath }
    Invoke-Python scripts/build_windows.py
    Invoke-Python scripts/package_release.py
    Invoke-Python scripts/stage_distribution_materials.py
    $Compiler = "$ProjectRoot/build/nsis-portable/nsis-3.13/makensis.exe"
    Invoke-Python scripts/review_distribution.py --compiler-license "$ProjectRoot/build/nsis-portable/nsis-3.13/COPYING"
    Invoke-Python scripts/build_installer.py --compiler $Compiler --legal-dir installer/public
    $Version = & $Python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])"
    & "./dist/$Version/AIDA-FPS-Studio/AIDA-FPS-Studio.exe" --self-test "$ProjectRoot/build/self-test"
    if ($LASTEXITCODE -ne 0) { throw 'Frozen self-test failed' }
    Invoke-Python scripts/finalize_artifacts.py
} finally { Pop-Location }
