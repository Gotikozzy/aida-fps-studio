param(
    [string]$Python = 'python',
    [ValidateSet('all', 'prepare', 'media', 'native', 'test', 'freeze', 'legal', 'installer', 'smoke', 'finalize')]
    [string]$Stage = 'all'
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$ProjectRoot = Split-Path $PSScriptRoot -Parent
Push-Location $ProjectRoot
try {
    function Invoke-Python {
        & $Python @args
        if ($LASTEXITCODE -ne 0) { throw "Python command failed: $args" }
    }
    $Stages = @('prepare', 'media', 'native', 'test', 'freeze', 'legal', 'installer', 'smoke', 'finalize')
    foreach ($CurrentStage in $Stages) {
        if ($Stage -ne 'all' -and $Stage -ne $CurrentStage) { continue }
        Write-Output "::group::Candidate stage: $CurrentStage"
        try {
            switch ($CurrentStage) {
                'prepare' {
                    Invoke-Python scripts/verify_source_integrity.py
                    Invoke-Python scripts/bootstrap_sources.py --extract
                    # Extract the verified compiler as data, never execute its downloaded EXE.
                    $SevenZip = (Get-Command 7z.exe -ErrorAction Stop).Source
                    & $SevenZip x build/lgpl-native/w64devkit-x64-2.11.0.7z.exe '-obuild/lgpl-native/toolchain' -y
                    if ($LASTEXITCODE -ne 0) { throw 'Toolchain extraction failed' }
                }
                'media' {
                    Invoke-Python scripts/build_lgpl_ffmpeg.py
                    Invoke-Python scripts/prepare_lgpl_runtime.py build/lgpl-native/prefix/bin build/lgpl-native/site
                }
                'native' { Invoke-Python scripts/build_nvidia.py }
                'test' {
                    $PreviousPythonPath = $env:PYTHONPATH
                    try {
                        $env:PYTHONPATH = "$ProjectRoot/build/lgpl-native/site;$ProjectRoot/src"
                        Invoke-Python -m pytest -q --junitxml=build/candidate-test-results.xml
                    } finally { $env:PYTHONPATH = $PreviousPythonPath }
                }
                'freeze' {
                    Invoke-Python scripts/build_windows.py
                    Invoke-Python scripts/package_release.py
                }
                'legal' {
                    Invoke-Python scripts/stage_distribution_materials.py
                    Invoke-Python scripts/review_distribution.py --compiler-license "$ProjectRoot/build/nsis-portable/nsis-3.13/COPYING"
                }
                'installer' {
                    Invoke-Python scripts/build_installer.py --compiler "$ProjectRoot/build/nsis-portable/nsis-3.13/makensis.exe" --legal-dir installer/public
                }
                'smoke' {
                    $Version = & $Python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])"
                    if ($LASTEXITCODE -ne 0) { throw 'Cannot read product version' }
                    $Executable = Join-Path $ProjectRoot "dist/$Version/AIDA-FPS-Studio/AIDA-FPS-Studio.exe"
                    $OutputPath = Join-Path $ProjectRoot 'build/self-test'
                    $Process = Start-Process -FilePath $Executable -ArgumentList @('--self-test', ('"' + $OutputPath + '"')) -Wait -PassThru -WindowStyle Hidden
                    if ($Process.ExitCode -ne 0) { throw 'Frozen self-test failed' }
                    $Result = Get-Content -LiteralPath (Join-Path $OutputPath 'self-test.json') -Raw | ConvertFrom-Json
                    if ($Result.status -ne 'passed') { throw 'Frozen self-test report did not pass' }
                }
                'finalize' { Invoke-Python scripts/finalize_artifacts.py }
            }
        } finally { Write-Output '::endgroup::' }
    }
} finally { Pop-Location }
