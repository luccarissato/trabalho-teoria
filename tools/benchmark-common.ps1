Set-StrictMode -Version Latest

function ConvertTo-ProcessArgument {
    param([Parameter(Mandatory = $true)][string]$Value)

    if ($Value -notmatch '[\s"]') {
        return $Value
    }
    return '"' + $Value.Replace('"', '\"') + '"'
}

function Resolve-PythonExecutable {
    param([string]$Command = 'python')

    $resolved = & $Command -c "import sys; print(sys.executable)" 2>$null
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace(($resolved -join ''))) {
        throw "Nao foi possivel localizar o executavel real do Python a partir de '$Command'."
    }
    return ($resolved | Select-Object -First 1).Trim()
}

function Invoke-DirectProcess {
    param(
        [Parameter(Mandatory = $true)][string]$FileName,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][int]$TimeoutSeconds
    )

    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $FileName
    $startInfo.Arguments = (($Arguments | ForEach-Object { ConvertTo-ProcessArgument $_ }) -join ' ')
    $startInfo.WorkingDirectory = (Get-Location).Path
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $startInfo.StandardErrorEncoding = [System.Text.Encoding]::UTF8

    $process = $null
    try {
        for ($attempt = 1; $attempt -le 60; $attempt++) {
            $candidate = New-Object System.Diagnostics.Process
            $candidate.StartInfo = $startInfo
            try {
                if ($candidate.Start()) {
                    $process = $candidate
                    break
                }
                throw "O processo nao iniciou."
            }
            catch {
                $startError = $_
                $candidate.Dispose()
                if ($attempt -eq 60) { throw $startError }
                Start-Sleep -Milliseconds 500
            }
        }
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
        $peakWorkingSet = 0L
        $peakPagedMemory = 0L
        $completed = $false
        do {
            try {
                $process.Refresh()
                if (-not $process.HasExited) {
                    $peakWorkingSet = [Math]::Max($peakWorkingSet, [long]$process.PeakWorkingSet64)
                    $peakPagedMemory = [Math]::Max($peakPagedMemory, [long]$process.PeakPagedMemorySize64)
                }
            } catch {}
            $completed = $process.WaitForExit(10)
        } while (-not $completed -and $stopwatch.Elapsed.TotalSeconds -lt $TimeoutSeconds)
        if (-not $completed) {
            $process.Kill()
            $process.WaitForExit()
        }
        $process.Refresh()
        $stdout = $stdoutTask.GetAwaiter().GetResult()
        $stderr = $stderrTask.GetAwaiter().GetResult()
        $exitCode = if ($completed) { $process.ExitCode } else { $null }
        return [pscustomobject]@{
            Status = if ($completed) { 'completed' } else { 'timeout' }
            ExitCode = $exitCode
            StandardOutput = $stdout.Trim()
            StandardError = $stderr.Trim()
            PeakWorkingSet64 = $peakWorkingSet
            PeakPagedMemorySize64 = $peakPagedMemory
        }
    }
    catch {
        return [pscustomobject]@{
            Status = 'failed'
            ExitCode = $null
            StandardOutput = ''
            StandardError = $_.Exception.Message
            PeakWorkingSet64 = $null
            PeakPagedMemorySize64 = $null
        }
    }
    finally {
        if ($null -ne $process) { $process.Dispose() }
    }
}

function Get-DatasetFiles {
    param(
        [Parameter(Mandatory = $true)][string]$ProjectRoot,
        [string[]]$Datasets
    )

    if ($Datasets -and @($Datasets).Count -gt 0) {
        return @($Datasets | ForEach-Object {
            $candidate = if ([System.IO.Path]::IsPathRooted($_)) { $_ } else { Join-Path $ProjectRoot $_ }
            (Resolve-Path -LiteralPath $candidate -ErrorAction Stop).Path
        })
    }
    return @(Get-ChildItem -LiteralPath (Join-Path $ProjectRoot 'datasets') -Filter '*.graph' -File |
        Sort-Object Name | ForEach-Object { $_.FullName })
}

function Write-EnvironmentManifest {
    param(
        [Parameter(Mandatory = $true)][string]$ProjectRoot,
        [Parameter(Mandatory = $true)][string]$PythonExecutable,
        [Parameter(Mandatory = $true)][string]$OutputPath,
        [string]$CompilerFlags = '-std=c17 -O2 -Wall -Wextra -Wpedantic'
    )

    try {
        $processorName = (Get-ItemProperty -LiteralPath 'HKLM:\HARDWARE\DESCRIPTION\System\CentralProcessor\0' -ErrorAction Stop).ProcessorNameString.Trim()
    } catch {
        $processorName = $env:PROCESSOR_IDENTIFIER
    }
    $ramBytes = $null
    try {
        Add-Type -AssemblyName Microsoft.VisualBasic -ErrorAction Stop
        $computerInfo = New-Object Microsoft.VisualBasic.Devices.ComputerInfo
        $ramBytes = [long]$computerInfo.TotalPhysicalMemory
    } catch {}

    $gccVersion = (& gcc --version 2>$null | Select-Object -First 1)
    $pythonVersion = (& $PythonExecutable --version 2>&1 | Select-Object -First 1)
    $jitCode = "import sys; j=getattr(sys, '_jit', None); print('unavailable' if j is None else ('enabled' if j.is_enabled() else 'disabled'))"
    $jitState = (& $PythonExecutable -c $jitCode 2>$null | Select-Object -First 1)
    if ([string]::IsNullOrWhiteSpace($jitState)) { $jitState = 'unknown' }

    Push-Location $ProjectRoot
    try {
        $commit = (git rev-parse HEAD 2>$null | Select-Object -First 1)
        $dirty = -not [string]::IsNullOrWhiteSpace(((git status --porcelain 2>$null) -join ''))
        $powerMode = (powercfg /getactivescheme 2>$null | Select-Object -First 1)
    }
    finally {
        Pop-Location
    }

    $manifest = [ordered]@{
        schema_version = 1
        collected_at = [DateTimeOffset]::Now.ToString('o')
        commit = $commit
        tracked_worktree_dirty = $dirty
        cpu = $processorName
        logical_processors = [Environment]::ProcessorCount
        ram_bytes = $ramBytes
        operating_system = [Environment]::OSVersion.VersionString
        operating_system_version = [Environment]::OSVersion.Version.ToString()
        powershell = $PSVersionTable.PSVersion.ToString()
        gcc = $gccVersion
        c_standard = 'C17'
        compiler_flags = $CompilerFlags
        python = $pythonVersion
        python_executable = $PythonExecutable
        python_jit = $jitState
        power_mode = $powerMode
        timers = [ordered]@{
            c_windows = 'QueryPerformanceCounter'
            c_linux = 'clock_gettime(CLOCK_MONOTONIC)'
            python = 'time.perf_counter_ns'
        }
        timeout_seconds = 60
        timing_repetitions = 20
        memory_repetitions = 15
    }

    $parent = Split-Path -Parent $OutputPath
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($OutputPath, (($manifest | ConvertTo-Json -Depth 6) + "`n"), $utf8NoBom)
}

function Get-Median {
    param([Parameter(Mandatory = $true)][AllowEmptyCollection()][double[]]$Values)

    $sorted = @($Values | Sort-Object)
    if ($sorted.Count -eq 0) { return $null }
    $middle = [int][Math]::Floor($sorted.Count / 2)
    if ($sorted.Count % 2 -eq 1) { return [double]$sorted[$middle] }
    return ([double]$sorted[$middle - 1] + [double]$sorted[$middle]) / 2.0
}

function Get-Average {
    param([Parameter(Mandatory = $true)][AllowEmptyCollection()][double[]]$Values)

    if ($Values.Count -eq 0) { return $null }
    return [double](($Values | Measure-Object -Average).Average)
}

function Get-SampleStandardDeviation {
    param([Parameter(Mandatory = $true)][AllowEmptyCollection()][double[]]$Values)

    if ($Values.Count -lt 2) { return 0.0 }
    $average = Get-Average $Values
    $sum = 0.0
    foreach ($value in $Values) {
        $difference = $value - $average
        $sum += $difference * $difference
    }
    return [Math]::Sqrt($sum / ($Values.Count - 1))
}
