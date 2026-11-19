[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$cExecutable = Join-Path $projectRoot 'c\bin\graph_solver.exe'

Write-Host '1/7 - Gerando e congelando datasets experimentais'
python .\tools\generate_experiments.py --root .\datasets --seed 20261117
if ($LASTEXITCODE -ne 0) { throw 'Falha na geração dos datasets.' }

Write-Host '2/7 - Compilando C17'
New-Item -ItemType Directory -Force .\c\bin | Out-Null
gcc -std=c17 -O2 -Wall -Wextra -Wpedantic .\c\src\main.c -o .\c\bin\graph_solver.exe
if ($LASTEXITCODE -ne 0) { throw 'Falha na compilação C17.' }

$pilot = @(Get-ChildItem .\datasets\pilot -Filter '*.graph' | Sort-Object Name | ForEach-Object FullName)
$paired = @(Get-ChildItem .\datasets\paired -Filter '*.graph' | Sort-Object Name | ForEach-Object FullName)
$pairedPaths = @(Get-ChildItem .\datasets\paired -Filter 'path_*.graph' | Sort-Object Name | ForEach-Object FullName)
$eulerianScale = @(Get-ChildItem .\datasets\eulerian-scale -Filter '*.graph' | Sort-Object Name | ForEach-Object FullName)

Write-Host '3/7 - Executando piloto hamiltoniano (timeout de 60 s)'
& .\tools\run-benchmarks.ps1 `
    -Datasets $pilot `
    -Problems hamiltonian `
    -Repetitions 1 `
    -Warmups 0 `
    -BatchSize 1 `
    -TimeoutSeconds 60 `
    -CExecutable $cExecutable `
    -OutputPath .\results\raw\pilot_timing.csv `
    -ManifestPath .\results\manifest.json

Write-Host '4/7 - Executando campanha pareada de tempo'
& .\tools\run-benchmarks.ps1 `
    -Datasets $paired `
    -Problems eulerian,hamiltonian `
    -Repetitions 20 `
    -Warmups 3 `
    -TimeoutSeconds 60 `
    -CExecutable $cExecutable `
    -OutputPath .\results\raw\paired_timing.csv `
    -ManifestPath .\results\manifest.json

Write-Host '5/7 - Executando campanha de escala de Hierholzer'
& .\tools\run-benchmarks.ps1 `
    -Datasets $eulerianScale `
    -Problems eulerian `
    -Repetitions 20 `
    -Warmups 3 `
    -TimeoutSeconds 60 `
    -CExecutable $cExecutable `
    -OutputPath .\results\raw\eulerian_scale_timing.csv `
    -ManifestPath .\results\manifest.json

Write-Host '6/7 - Medindo memória em processos separados'
& .\tools\measure-memory.ps1 `
    -Datasets $pairedPaths `
    -Problems eulerian,hamiltonian `
    -Repetitions 15 `
    -TimeoutSeconds 60 `
    -CExecutable $cExecutable `
    -OutputPath .\results\raw\paired_memory.csv `
    -SummaryPath .\tmp\stage3\paired_memory_preliminary.csv
& .\tools\measure-memory.ps1 `
    -Datasets $eulerianScale `
    -Problems eulerian `
    -Repetitions 15 `
    -TimeoutSeconds 60 `
    -CExecutable $cExecutable `
    -OutputPath .\results\raw\eulerian_scale_memory.csv `
    -SummaryPath .\tmp\stage3\eulerian_scale_memory_preliminary.csv

Write-Host '7/7 - Validando, resumindo e gerando gráficos SVG'
python .\tools\analyze.py `
    --timing .\results\raw\paired_timing.csv .\results\raw\eulerian_scale_timing.csv `
    --memory .\results\raw\paired_memory.csv .\results\raw\eulerian_scale_memory.csv `
    --pilot .\results\raw\pilot_timing.csv `
    --datasets-manifest .\datasets\experimental-manifest.json `
    --output .\results `
    --expected-timing-repetitions 20 `
    --expected-memory-repetitions 15
if ($LASTEXITCODE -ne 0) { throw 'Falha na análise experimental.' }

Write-Host 'Campanha experimental concluída.'
