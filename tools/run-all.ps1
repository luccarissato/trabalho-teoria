[CmdletBinding()]
param(
    [switch]$Quick,
    [switch]$Full
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (($Quick -and $Full) -or (-not $Quick -and -not $Full)) {
    throw 'Escolha exatamente um modo: -Quick ou -Full.'
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$cExecutable = Join-Path $projectRoot 'c\bin\graph_solver.exe'
$validationRoot = Join-Path $projectRoot 'tmp\run-all'
Set-Location -LiteralPath $projectRoot

function Invoke-Checked {
    param(
        [string]$Label,
        [scriptblock]$Action
    )
    Write-Host "`n--- $Label ---"
    $global:LASTEXITCODE = 0
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "$Label falhou com código $LASTEXITCODE."
    }
    Write-Host "PASS: $Label"
}

function Assert-GeneratedPath {
    param([string]$Path)
    $resolvedRoot = [System.IO.Path]::GetFullPath($projectRoot).TrimEnd('\')
    $resolvedPath = [System.IO.Path]::GetFullPath((Join-Path $projectRoot $Path))
    if (-not $resolvedPath.StartsWith(($resolvedRoot + '\'), [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Caminho gerado fora do projeto: $resolvedPath"
    }
    return $resolvedPath
}

function Build-And-Test {
    Invoke-Checked 'Compilação C17 com avisos habilitados' {
        New-Item -ItemType Directory -Force .\c\bin | Out-Null
        # O GCC/MSYS2 pode falhar ao receber o caminho absoluto quando a pasta contém acentos.
        gcc -std=c17 -O2 -Wall -Wextra -Wpedantic .\c\src\main.c -o .\c\bin\graph_solver.exe
    }
    Invoke-Checked 'Testes de corretude cruzados' {
        for ($attempt = 1; $attempt -le 3; $attempt++) {
            python .\tests\correctness.py --c $cExecutable
            if ($LASTEXITCODE -eq 0) { break }
            if ($attempt -lt 3) {
                Write-Warning "Controle de Aplicativo bloqueou uma execução; nova tentativa $($attempt + 1)/3."
                Start-Sleep -Seconds 2
            }
        }
    }
}

$verificationArguments = @('--root', $projectRoot)
if ($Quick) {
    if (Test-Path -LiteralPath $validationRoot) {
        Remove-Item -LiteralPath $validationRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Force $validationRoot | Out-Null

    Build-And-Test

    Invoke-Checked 'Regeneração determinística dos 29 datasets' {
        $temporaryDatasets = Join-Path $validationRoot 'datasets'
        python .\tools\generate_experiments.py --root $temporaryDatasets --seed 20261117
        if ($LASTEXITCODE -ne 0) { throw 'Falha na geração dos datasets.' }
        $official = Get-Content .\datasets\experimental-manifest.json -Raw -Encoding UTF8 | ConvertFrom-Json
        $regenerated = Get-Content (Join-Path $temporaryDatasets 'experimental-manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($official.graph_count -ne 29 -or $regenerated.graph_count -ne 29) {
            throw 'A suíte experimental deve conter exatamente 29 grafos.'
        }
        foreach ($entry in $official.graphs) {
            $other = @($regenerated.graphs | Where-Object { $_.file -eq $entry.file })
            if ($other.Count -ne 1 -or $other[0].sha256 -ne $entry.sha256) {
                throw "Dataset não determinístico: $($entry.file)"
            }
        }
    }

    Invoke-Checked 'Amostra curta de tempo' {
        & .\tools\run-benchmarks.ps1 `
            -Datasets .\datasets\paired\path_v008.graph `
            -Problems eulerian,hamiltonian `
            -Repetitions 2 `
            -Warmups 1 `
            -BatchSize 1 `
            -TimeoutSeconds 60 `
            -CExecutable $cExecutable `
            -OutputPath (Join-Path $validationRoot 'quick_timing.csv') `
            -ManifestPath (Join-Path $validationRoot 'quick_environment.json')
        $timingRows = @(Import-Csv -LiteralPath (Join-Path $validationRoot 'quick_timing.csv'))
        $invalidTiming = @($timingRows | Where-Object { $_.status -ne 'completed' -or $_.valid -ne 'True' })
        if ($timingRows.Count -ne 8 -or $invalidTiming.Count -ne 0) {
            throw "A amostra de tempo não produziu oito observações válidas (inválidas: $($invalidTiming.Count))."
        }
        $global:LASTEXITCODE = 0
    }

    Invoke-Checked 'Amostra curta de memória por processo' {
        & .\tools\measure-memory.ps1 `
            -Datasets .\datasets\paired\path_v008.graph `
            -Problems eulerian,hamiltonian `
            -Repetitions 2 `
            -TimeoutSeconds 60 `
            -CExecutable $cExecutable `
            -OutputPath (Join-Path $validationRoot 'quick_memory.csv') `
            -SummaryPath (Join-Path $validationRoot 'quick_memory_summary.csv')
        $memoryRows = @(Import-Csv -LiteralPath (Join-Path $validationRoot 'quick_memory.csv'))
        $invalidMemory = @($memoryRows | Where-Object { $_.status -ne 'completed' -or [long]$_.peak_working_set_bytes -le 0 })
        if ($memoryRows.Count -ne 16 -or $invalidMemory.Count -ne 0) {
            throw "A amostra de memória não produziu 16 observações válidas (inválidas: $($invalidMemory.Count))."
        }
        $global:LASTEXITCODE = 0
    }

    $analysisRoot = Join-Path $validationRoot 'analysis'
    Invoke-Checked 'Regeneração das tabelas e dos gráficos' {
        $publishedAnalysis = Get-Content .\results\analysis-manifest.json -Raw -Encoding UTF8 | ConvertFrom-Json
        python .\tools\analyze.py `
            --timing .\results\raw\paired_timing.csv .\results\raw\eulerian_scale_timing.csv `
            --memory .\results\raw\paired_memory.csv .\results\raw\eulerian_scale_memory.csv `
            --pilot .\results\raw\pilot_timing.csv `
            --pilot-timeout-seconds $publishedAnalysis.pilot_timeout_seconds `
            --datasets-manifest .\datasets\experimental-manifest.json `
            --output $analysisRoot `
            --expected-timing-repetitions 20 `
            --expected-memory-repetitions 15
    }
    $verificationArguments += @('--reproduced-analysis', $analysisRoot)
} else {
    Build-And-Test
    Write-Host "`n--- Remoção controlada somente de artefatos experimentais gerados ---"
    $generatedPaths = @(
        'datasets\paired',
        'datasets\pilot',
        'datasets\eulerian-scale',
        'datasets\experimental-manifest.json',
        'results\raw',
        'results\summary',
        'results\charts',
        'results\analysis-manifest.json',
        'results\manifest.json',
        'results\final-manifest.json'
    )
    foreach ($relativePath in $generatedPaths) {
        $target = Assert-GeneratedPath $relativePath
        if (Test-Path -LiteralPath $target) {
            Remove-Item -LiteralPath $target -Recurse -Force
        }
    }
    Invoke-Checked 'Campanha experimental integral' {
        & .\tools\run-experiments.ps1
    }
    Invoke-Checked 'Manifesto final de reprodutibilidade' {
        python .\tools\create_final_manifest.py --root $projectRoot
    }
}

Invoke-Checked 'Validação dos dados e artefatos experimentais' {
    python .\tools\verify_project.py @verificationArguments
}

$modeName = if ($Quick) { 'Quick' } else { 'Full' }
Write-Host "`nRESULTADO FINAL: PASS ($modeName)"
