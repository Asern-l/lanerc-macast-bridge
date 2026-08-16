$ErrorActionPreference = 'Stop'

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$macastDir = Join-Path $env:LOCALAPPDATA 'xfangfang\Macast'
$rendererDir = Join-Path $macastDir 'renderer'
$settingsPath = Join-Path $macastDir 'macast_setting.json'
$backupDir = Join-Path $macastDir 'backup'

New-Item -ItemType Directory -Force $rendererDir | Out-Null
Copy-Item -Force (Join-Path $projectDir 'lanerc_proxy.py') (Join-Path $rendererDir 'lanerc_proxy.py')
Copy-Item -Force (Join-Path $projectDir 'lanerc_potplayer.py') (Join-Path $rendererDir 'lanerc_potplayer.py')

$potPlayerCandidates = @(
    'D:\PotPlayer\PotPlayerMini64.exe',
    'D:\PotPlayer\PotPlayerMini.exe',
    'C:\Program Files\DAUM\PotPlayer\PotPlayerMini64.exe',
    'C:\Program Files (x86)\DAUM\PotPlayer\PotPlayerMini.exe',
    'C:\Program Files\PotPlayer\PotPlayerMini64.exe'
)

foreach ($registryPath in @('HKCU:\Software\DAUM\PotPlayer64', 'HKCU:\Software\DAUM\PotPlayer')) {
    try {
        $programPath = (Get-ItemProperty -LiteralPath $registryPath -Name ProgramPath -ErrorAction Stop).ProgramPath
        if ($programPath) {
            $potPlayerCandidates = @($programPath) + $potPlayerCandidates
        }
    } catch {
        # PotPlayer is not registered under this key.
    }
}

$potPlayer = $potPlayerCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
$selectedRenderer = if ($potPlayer) { 'Lanerc PotPlayer Renderer' } else { 'Lanerc MPV Renderer' }

if (Test-Path $settingsPath) {
    New-Item -ItemType Directory -Force $backupDir | Out-Null
    $timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    Copy-Item -LiteralPath $settingsPath -Destination (Join-Path $backupDir "macast_setting-$timestamp.json")

    $settings = Get-Content -Raw $settingsPath | ConvertFrom-Json
    $settings | Add-Member -NotePropertyName Macast_Renderer -NotePropertyValue $selectedRenderer -Force
    $json = $settings | ConvertTo-Json -Depth 10
    [IO.File]::WriteAllText($settingsPath, $json, [Text.UTF8Encoding]::new($false))
}

Write-Host "Installed renderers in: $rendererDir"
Write-Host "Macast renderer selected: $selectedRenderer"
Write-Host 'Exit Macast completely and start it again to load the plugin.'
