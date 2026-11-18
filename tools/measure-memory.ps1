[CmdletBinding()]
param(
    [string[]]$Datasets,
    [ValidateSet('eulerian', 'hamiltonian')][string[]]$Problems = @('eulerian', 'hamiltonian'),
    [ValidateRange(1, 1000)][int]$Repetitions = 15,
    [ValidateRange(1, 86400)][int]$TimeoutSeconds = 60,
    [string]$CExecutable,
    [string]$PythonCommand = 'python',
    [string]$OutputPath,
    [string]$SummaryPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'benchmark-common.ps1')

if ([string]::IsNullOrWhiteSpace($CExecutable)) {
    $CExecutable = Join-Path $projectRoot 'c\bin\graph_solver.exe'
}
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Join-Path $projectRoot 'results\raw\memory.csv'
} elseif (-not [System.IO.Path]::IsPathRooted($OutputPath)) {
    $OutputPath = Join-Path $projectRoot $OutputPath
}
if ([string]::IsNullOrWhiteSpace($SummaryPath)) {
    $SummaryPath = Join-Path $projectRoot 'results\summary\memory.csv'
} elseif (-not [System.IO.Path]::IsPathRooted($SummaryPath)) {
    $SummaryPath = Join-Path $projectRoot $SummaryPath
}

$CExecutable = (Resolve-Path -LiteralPath $CExecutable -ErrorAction Stop).Path
$pythonExecutable = Resolve-PythonExecutable $PythonCommand
$pythonMain = Join-Path $projectRoot 'python\src\main.py'
$datasetFiles = @(Get-DatasetFiles -ProjectRoot $projectRoot -Datasets $Datasets)
if ($datasetFiles.Count -eq 0) {
    throw 'Nenhum dataset .graph foi encontrado.'
}
$commit = (git -C $projectRoot rev-parse HEAD | Select-Object -First 1).Trim()
$rows = New-Object System.Collections.Generic.List[object]

function Get-RelativeDatasetPath {
    param([string]$Path)
    $rootUri = New-Object System.Uri(($projectRoot.TrimEnd('\') + '\'))
    $pathUri = New-Object System.Uri($Path)
    return [System.Uri]::UnescapeDataString($rootUri.MakeRelativeUri($pathUri).ToString())
}

function Invoke-MemoryPoint {
    param(
        [string]$Language,
        [string]$Problem,
        [string]$Dataset,
        [bool]$Baseline
    )

    $arguments = @('--problem', $Problem, '--input', $Dataset, '--hold-ms', '100')
    if ($Baseline) { $arguments += '--baseline' }
    if ($Language -eq 'python') {
        $arguments = @($pythonMain) + $arguments
        return Invoke-DirectProcess -FileName $pythonExecutable -Arguments $arguments -TimeoutSeconds $TimeoutSeconds
    }
    return Invoke-DirectProcess -FileName $CExecutable -Arguments $arguments -TimeoutSeconds $TimeoutSeconds
}

foreach ($dataset in $datasetFiles) {
    foreach ($problem in $Problems) {
        foreach ($language in @('c', 'python')) {
            foreach ($mode in @('baseline', 'algorithm')) {
                for ($repetition = 1; $repetition -le $Repetitions; $repetition++) {
                    $execution = Invoke-MemoryPoint -Language $language -Problem $problem -Dataset $dataset -Baseline ($mode -eq 'baseline')
                    $status = $execution.Status
                    $data = $null
                    if ($status -eq 'completed' -and $execution.ExitCode -eq 0) {
                        try { $data = $execution.StandardOutput | ConvertFrom-Json }
                        catch { $status = 'invalid_json' }
                    } elseif ($status -eq 'completed') {
                        $status = 'failed'
                    }
                    $rows.Add([pscustomobject][ordered]@{
                        timestamp = [DateTimeOffset]::Now.ToString('o')
                        commit = $commit
                        language = $language
                        problem = $problem
                        dataset = Get-RelativeDatasetPath $dataset
                        family = if ($data) { $data.family } else { $null }
                        case = if ($data) { $data.case } else { $null }
                        seed = if ($data) { $data.seed } else { $null }
                        V = if ($data) { $data.vertices } else { $null }
                        E = if ($data) { $data.edges } else { $null }
                        mode = $mode
                        repetition = $repetition
                        peak_working_set_bytes = $execution.PeakWorkingSet64
                        peak_paged_memory_bytes = $execution.PeakPagedMemorySize64
                        status = $status
                        timeout = ($execution.Status -eq 'timeout')
                        exit_code = $execution.ExitCode
                        error = $execution.StandardError
                    })
                }
            }
        }
    }
}

$outputParent = Split-Path -Parent $OutputPath
New-Item -ItemType Directory -Force -Path $outputParent | Out-Null
$rows | Export-Csv -LiteralPath $OutputPath -NoTypeInformation -Encoding UTF8

$summaries = New-Object System.Collections.Generic.List[object]
$points = $rows | Select-Object language, problem, dataset -Unique
foreach ($point in $points) {
    $pointRows = @($rows | Where-Object {
        $_.language -eq $point.language -and
        $_.problem -eq $point.problem -and
        $_.dataset -eq $point.dataset -and
        $_.status -eq 'completed'
    })
    $baselineRows = @($pointRows | Where-Object { $_.mode -eq 'baseline' })
    $algorithmRows = @($pointRows | Where-Object { $_.mode -eq 'algorithm' })
    $baselineWorking = [double[]]@($baselineRows | ForEach-Object { [double]$_.peak_working_set_bytes })
    $algorithmWorking = [double[]]@($algorithmRows | ForEach-Object { [double]$_.peak_working_set_bytes })
    $baselinePaged = [double[]]@($baselineRows | ForEach-Object { [double]$_.peak_paged_memory_bytes })
    $algorithmPaged = [double[]]@($algorithmRows | ForEach-Object { [double]$_.peak_paged_memory_bytes })
    $baselineMedian = Get-Median $baselineWorking
    $algorithmMedian = Get-Median $algorithmWorking
    $summaries.Add([pscustomobject][ordered]@{
        language = $point.language
        problem = $point.problem
        dataset = $point.dataset
        baseline_count = $baselineWorking.Count
        algorithm_count = $algorithmWorking.Count
        baseline_peak_working_set_median_bytes = $baselineMedian
        baseline_peak_working_set_mean_bytes = Get-Average $baselineWorking
        baseline_peak_working_set_stddev_bytes = Get-SampleStandardDeviation $baselineWorking
        algorithm_peak_working_set_median_bytes = $algorithmMedian
        algorithm_peak_working_set_mean_bytes = Get-Average $algorithmWorking
        algorithm_peak_working_set_stddev_bytes = Get-SampleStandardDeviation $algorithmWorking
        approximate_increment_median_bytes = if ($null -ne $baselineMedian -and $null -ne $algorithmMedian) {
            [Math]::Max(0.0, $algorithmMedian - $baselineMedian)
        } else { $null }
        baseline_peak_paged_median_bytes = Get-Median $baselinePaged
        algorithm_peak_paged_median_bytes = Get-Median $algorithmPaged
    })
}

$summaryParent = Split-Path -Parent $SummaryPath
New-Item -ItemType Directory -Force -Path $summaryParent | Out-Null
$summaries | Export-Csv -LiteralPath $SummaryPath -NoTypeInformation -Encoding UTF8

$completedRows = @($rows | Where-Object { $_.status -eq 'completed' }).Count
$timeoutRows = @($rows | Where-Object { $_.timeout }).Count
Write-Output "CSV bruto de memoria: $OutputPath"
Write-Output "Resumo de memoria: $SummaryPath"
Write-Output "Linhas: $($rows.Count); concluidas: $completedRows; timeouts: $timeoutRows"
