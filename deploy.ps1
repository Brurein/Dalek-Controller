param(
    [ValidateSet("all", "sender", "receiver")]
    [string]$Target = "all",

    [string]$SenderPort = "",
    [string]$ReceiverPort = "",

    [string]$InitSenderPort = "",
    [string]$InitReceiverPort = "",

    [switch]$List,
    [switch]$KillPutty,

    [ValidateSet("none", "sender", "receiver")]
    [string]$Repl = "none",

    [switch]$OpenPutty,
    [string]$PuttyPath = "putty.exe"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoRoot

$ValidDeviceIds = @("sender", "receiver")

$DeployFiles = @{
    sender = @(
        @{ Source = "sender\code-sender.py"; Destination = ":main.py" },
        @{ Source = "sender\device-id.txt"; Destination = ":device-id.txt" }
    )
    receiver = @(
        @{ Source = "receiver\code-receiver.py"; Destination = ":main.py" },
        @{ Source = "receiver\amp.py"; Destination = ":amp.py" },
        @{ Source = "receiver\commands.py"; Destination = ":commands.py" },
        @{ Source = "receiver\config_loader.py"; Destination = ":config_loader.py" },
        @{ Source = "receiver\inputs.py"; Destination = ":inputs.py" },
        @{ Source = "receiver\lights.py"; Destination = ":lights.py" },
        @{ Source = "receiver\sound.py"; Destination = ":sound.py" },
        @{ Source = "receiver\config.json"; Destination = ":config.json" },
        @{ Source = "receiver\device-id.txt"; Destination = ":device-id.txt" }
    )
}

function Assert-Mpremote {
    $cmd = Get-Command mpremote -ErrorAction SilentlyContinue
    if (-not $cmd) {
        throw "mpremote was not found on PATH. Install it with: python -m pip install mpremote"
    }
}

function Invoke-Mpremote {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Port,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [switch]$AllowFailure
    )

    $output = & mpremote connect $Port @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    $text = ($output | ForEach-Object { $_.ToString() }) -join "`n"

    if ($exitCode -ne 0 -and -not $AllowFailure) {
        throw "mpremote failed on $Port with args '$($Arguments -join ' ')':`n$text"
    }

    return @{
        ExitCode = $exitCode
        Text = $text
    }
}

function Get-ComPorts {
    [System.IO.Ports.SerialPort]::GetPortNames() |
        Sort-Object { [int](($_ -replace "[^\d]", "") -replace "^$", "0") }
}

function Read-DeviceId {
    param([Parameter(Mandatory = $true)][string]$Port)

    $result = Invoke-Mpremote -Port $Port -Arguments @("fs", "cat", "device-id.txt") -AllowFailure
    if ($result.ExitCode -ne 0) {
        return $null
    }

    foreach ($line in ($result.Text -split "\r?\n")) {
        $id = $line.Trim().ToLower()
        if ($ValidDeviceIds -contains $id) {
            return $id
        }
    }

    return $null
}

function Find-Devices {
    $devices = @{}
    $duplicates = @{}

    foreach ($port in Get-ComPorts) {
        Write-Host "Probing $port..."
        $id = Read-DeviceId -Port $port

        if (-not $id) {
            Write-Host "  no device-id.txt found"
            continue
        }

        Write-Host "  found $id"

        if ($devices.ContainsKey($id)) {
            if (-not $duplicates.ContainsKey($id)) {
                $duplicates[$id] = @($devices[$id])
            }
            $duplicates[$id] += $port
        } else {
            $devices[$id] = $port
        }
    }

    if ($duplicates.Count -gt 0) {
        foreach ($id in $duplicates.Keys) {
            Write-Host "Duplicate $id devices found: $($duplicates[$id] -join ', ')"
        }
        throw "Duplicate device identities found. Refusing to guess."
    }

    return $devices
}

function Stop-Putty {
    Write-Host "Stopping PuTTY..."
    Get-Process "*putty*" -ErrorAction SilentlyContinue | Stop-Process -Force
}

function Copy-DeviceFiles {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet("sender", "receiver")]
        [string]$DeviceId,

        [Parameter(Mandatory = $true)]
        [string]$Port
    )

    Write-Host "Deploying $DeviceId to $Port..."

    foreach ($file in $DeployFiles[$DeviceId]) {
        if (-not (Test-Path $file.Source)) {
            throw "Missing local file: $($file.Source)"
        }

        Write-Host "  $($file.Source) -> $($file.Destination)"
        Invoke-Mpremote -Port $Port -Arguments @("fs", "cp", $file.Source, $file.Destination) | Out-Null
    }

    Write-Host "  soft reset"
    Invoke-Mpremote -Port $Port -Arguments @("reset") -AllowFailure | Out-Null
}

function Write-DeviceIdentity {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet("sender", "receiver")]
        [string]$DeviceId,

        [Parameter(Mandatory = $true)]
        [string]$Port
    )

    $source = Join-Path $DeviceId "device-id.txt"
    if (-not (Test-Path $source)) {
        throw "Missing local identity file: $source"
    }

    Write-Host "Writing $DeviceId identity to $Port..."
    Invoke-Mpremote -Port $Port -Arguments @("fs", "cp", $source, ":device-id.txt") | Out-Null
}

function Open-Repl {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Port
    )

    Write-Host "Opening mpremote REPL on $Port..."
    & mpremote connect $Port repl
}

function Start-Putty {
    param([Parameter(Mandatory = $true)][string]$Port)

    Write-Host "Starting PuTTY on $Port..."
    Start-Process -FilePath $PuttyPath -ArgumentList "-serial", $Port, "-sercfg", "115200,8,n,1,N"
}

Assert-Mpremote

if ($KillPutty) {
    Stop-Putty
}

if ($InitSenderPort) {
    Write-DeviceIdentity -DeviceId sender -Port $InitSenderPort
}

if ($InitReceiverPort) {
    Write-DeviceIdentity -DeviceId receiver -Port $InitReceiverPort
}

$devices = Find-Devices

if ($SenderPort) {
    $devices["sender"] = $SenderPort
}

if ($ReceiverPort) {
    $devices["receiver"] = $ReceiverPort
}

Write-Host ""
Write-Host "Detected devices:"
foreach ($id in $ValidDeviceIds) {
    if ($devices.ContainsKey($id)) {
        Write-Host "  $id -> $($devices[$id])"
    } else {
        Write-Host "  $id -> not found"
    }
}

if ($List) {
    return
}

$targets = if ($Target -eq "all") { @("sender", "receiver") } else { @($Target) }

foreach ($id in $targets) {
    if (-not $devices.ContainsKey($id)) {
        throw "$id was not found. Add /device-id.txt to the device or pass -$($id.Substring(0, 1).ToUpper() + $id.Substring(1))Port COMx."
    }

    Copy-DeviceFiles -DeviceId $id -Port $devices[$id]
}

if ($OpenPutty) {
    foreach ($id in $targets) {
        Start-Putty -Port $devices[$id]
    }
}

if ($Repl -ne "none") {
    if (-not $devices.ContainsKey($Repl)) {
        throw "$Repl was not found; cannot open REPL."
    }
    Open-Repl -Port $devices[$Repl]
}

Write-Host "Done."
