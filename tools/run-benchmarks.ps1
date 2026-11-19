[CmdletBinding()]
param(
    [string[]]$Datasets,
    [ValidateSet('eulerian', 'hamiltonian')][string[]]$Problems = @('eulerian', 'hamiltonian'),
    [ValidateRange(1, 1000)][int]$Repetitions = 20,
    [ValidateRange(0, 1000)][int]$Warmups = 3,
    [ValidateRange(0, 1000000)][int]$BatchSize = 0,
    [ValidateRange(1, 1000000000)][long]$TargetBatchNanoseconds = 5000000,
    [ValidateRange(1, 1000000)][int]$MaximumBatchSize = 100000,
    [ValidateRange(1, 86400)][int]$TimeoutSeconds = 60,
    [string]$CExecutable,
    [string]$PythonCommand = 'python',
    [string]$OutputPath,
    [string]$ManifestPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'benchmark-common.ps1')

if ([string]::IsNullOrWhiteSpace($CExecutable)) {
    $CExecutable = Join-Path $projectRoot 'c\bin\graph_solver.exe'
}
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Join-Path $projectRoot 'results\raw\timing.csv'
} elseif (-not [System.IO.Path]::IsPathRooted($OutputPath)) {
    $OutputPath = Join-Path $projectRoot $OutputPath
}
if ([string]::IsNullOrWhiteSpace($ManifestPath)) {
    $ManifestPath = Join-Path $projectRoot 'results\manifest.json'
} elseif (-not [System.IO.Path]::IsPathRooted($ManifestPath)) {
    $ManifestPath = Join-Path $projectRoot $ManifestPath
}

$CExecutable = (Resolve-Path -LiteralPath $CExecutable -ErrorAction Stop).Path
$pythonExecutable = Resolve-PythonExecutable $PythonCommand
$pythonMain = Join-Path $projectRoot 'python\src\main.py'
$datasetFiles = @(Get-DatasetFiles -ProjectRoot $projectRoot -Datasets $Datasets)
if ($datasetFiles.Count -eq 0) {
    throw 'Nenhum dataset .graph foi encontrado.'
}

Write-EnvironmentManifest -ProjectRoot $projectRoot -PythonExecutable $pythonExecutable -OutputPath $ManifestPath
$commit = (git -C $projectRoot rev-parse HEAD | Select-Object -First 1).Trim()
$invariant = [System.Globalization.CultureInfo]::InvariantCulture
$rows = New-Object System.Collections.Generic.List[object]

function Get-RelativeDatasetPath {
    param([string]$Path)
    $rootUri = New-Object System.Uri(($projectRoot.TrimEnd('\') + '\'))
    $pathUri = New-Object System.Uri($Path)
    return [System.Uri]::UnescapeDataString($rootUri.MakeRelativeUri($pathUri).ToString())
}

function Get-GraphMetadata {
    param([string]$Path)
    $metadata = @{}
    foreach ($line in Get-Content -LiteralPath $Path -TotalCount 7 -Encoding UTF8) {
        if ($line -match '^(V|E|SEED|FAMILY|CASE)\s+(.+)$') {
            $metadata[$Matches[1]] = $Matches[2]
        }
    }
    return [pscustomobject]@{
        vertices = [long]$metadata['V']
        edges = [long]$metadata['E']
        seed = [long]$metadata['SEED']
        family = [string]$metadata['FAMILY']
        case_name = [string]$metadata['CASE']
    }
}

function Invoke-Solver {
    param(
        [string]$Language,
        [string]$Problem,
        [string]$Dataset,
        [int]$WarmupCount,
        [int]$MeasuredBatchSize
    )

    $arguments = @(
        '--problem', $Problem,
        '--input', $Dataset,
        '--warmups', [string]$WarmupCount,
        '--batch-size', [string]$MeasuredBatchSize
    )
    if ($Language -eq 'python') {
        $arguments = @($pythonMain) + $arguments
        return Invoke-DirectProcess -FileName $pythonExecutable -Arguments $arguments -TimeoutSeconds $TimeoutSeconds
    }
    return Invoke-DirectProcess -FileName $CExecutable -Arguments $arguments -TimeoutSeconds $TimeoutSeconds
}

foreach ($dataset in $datasetFiles) {
    $datasetMetadata = Get-GraphMetadata $dataset
    foreach ($problem in $Problems) {
        foreach ($language in @('c', 'python')) {
            $selectedBatchSize = $BatchSize
            if ($selectedBatchSize -eq 0) {
                $calibration = Invoke-Solver -Language $language -Problem $problem -Dataset $dataset -WarmupCount $Warmups -MeasuredBatchSize 1
                if ($calibration.Status -eq 'completed' -and $calibration.ExitCode -eq 0) {
                    try {
                        $calibrationData = $calibration.StandardOutput | ConvertFrom-Json
                        $singleCall = [Math]::Max(1.0, [double]$calibrationData.elapsed_ns_total)
                        $selectedBatchSize = [int][Math]::Ceiling($TargetBatchNanoseconds / $singleCall)
                        $selectedBatchSize = [Math]::Max(1, [Math]::Min($MaximumBatchSize, $selectedBatchSize))
                    }
                    catch {
                        $selectedBatchSize = 1
                    }
                } else {
                    $selectedBatchSize = 1
                }
            }

            for ($repetition = 1; $repetition -le $Repetitions; $repetition++) {
                $execution = Invoke-Solver -Language $language -Problem $problem -Dataset $dataset -WarmupCount $Warmups -MeasuredBatchSize $selectedBatchSize
                $status = $execution.Status
                $data = $null
                if ($status -eq 'completed' -and $execution.ExitCode -eq 0) {
                    try {
                        $data = $execution.StandardOutput | ConvertFrom-Json
                        if (-not $data.valid) { $status = 'invalid' }
                    }
                    catch {
                        $status = 'invalid_json'
                    }
                } elseif ($status -eq 'completed') {
                    $status = 'failed'
                }

                $vertices = if ($data) { [long]$data.vertices } else { $datasetMetadata.vertices }
                $edges = if ($data) { [long]$data.edges } else { $datasetMetadata.edges }
                $density = if ($vertices -gt 1) {
                    ((2.0 * $edges) / ($vertices * ($vertices - 1))).ToString('R', $invariant)
                } else { '0' }
                $rows.Add([pscustomobject][ordered]@{
                    timestamp = [DateTimeOffset]::Now.ToString('o')
                    commit = $commit
                    language = $language
                    problem = $problem
                    dataset = Get-RelativeDatasetPath $dataset
                    family = if ($data) { $data.family } else { $datasetMetadata.family }
                    case = if ($data) { $data.case } else { $datasetMetadata.case_name }
                    seed = if ($data) { $data.seed } else { $datasetMetadata.seed }
                    V = $vertices
                    E = $edges
                    density = $density
                    repetition = $repetition
                    warmups = $Warmups
                    batch_size = $selectedBatchSize
                    elapsed_ns = if ($data) { $data.elapsed_ns } else { $null }
                    elapsed_ns_total = if ($data) { $data.elapsed_ns_total } else { $null }
                    states_explored = if ($data) { $data.states_explored } else { $null }
                    edge_steps = if ($data) { $data.edge_steps } else { $null }
                    exists = if ($data) { $data.exists } else { $null }
                    status = $status
                    timeout = ($execution.Status -eq 'timeout')
                    valid = if ($data) { $data.valid } else { $false }
                    exit_code = $execution.ExitCode
                    error = $execution.StandardError
                })
            }
        }
    }
}

$parent = Split-Path -Parent $OutputPath
New-Item -ItemType Directory -Force -Path $parent | Out-Null
$rows | Export-Csv -LiteralPath $OutputPath -NoTypeInformation -Encoding UTF8

$completedRows = @($rows | Where-Object { $_.status -eq 'completed' }).Count
$timeoutRows = @($rows | Where-Object { $_.timeout }).Count
Write-Output "CSV de tempo: $OutputPath"
Write-Output "Linhas: $($rows.Count); concluidas: $completedRows; timeouts: $timeoutRows"
Write-Output "Manifesto: $ManifestPath"
