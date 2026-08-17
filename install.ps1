$ErrorActionPreference = 'Stop'

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$macastDir = Join-Path $env:LOCALAPPDATA 'xfangfang\Macast'
$rendererDir = Join-Path $macastDir 'renderer'
$settingsPath = Join-Path $macastDir 'macast_setting.json'
$backupDir = Join-Path $macastDir 'backup'

New-Item -ItemType Directory -Force $rendererDir | Out-Null
Copy-Item -Force (Join-Path $projectDir 'lanerc_proxy.py') (Join-Path $rendererDir 'lanerc_proxy.py')
Copy-Item -Force (Join-Path $projectDir 'lanerc_potplayer.py') (Join-Path $rendererDir 'lanerc_potplayer.py')
Copy-Item -Force (Join-Path $projectDir 'lanerc_tv.py') (Join-Path $rendererDir 'lanerc_tv.py')
Copy-Item -Force (Join-Path $projectDir 'lanerc_pro.py') (Join-Path $rendererDir 'lanerc_pro.py')
Copy-Item -Force (Join-Path $projectDir 'lanerc_pro.html') (Join-Path $rendererDir 'lanerc_pro.html')

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
$selectedRenderer = 'Lanerc Cast Pro'
$ffmpegCandidates = @(
    'D:\Macast\tools\ffmpeg\bin\ffmpeg.exe',
    'D:\ffmpeg\bin\ffmpeg.exe',
    'C:\ffmpeg\bin\ffmpeg.exe',
    (Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Links\ffmpeg.exe')
)
$ffmpegCommand = Get-Command ffmpeg.exe -ErrorAction SilentlyContinue
if ($ffmpegCommand) {
    $ffmpegCandidates = @($ffmpegCommand.Source) + $ffmpegCandidates
}
$ffmpeg = $ffmpegCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1

if (Test-Path $settingsPath) {
    New-Item -ItemType Directory -Force $backupDir | Out-Null
    $timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    Copy-Item -LiteralPath $settingsPath -Destination (Join-Path $backupDir "macast_setting-$timestamp.json")

    $settings = Get-Content -Raw $settingsPath | ConvertFrom-Json
    $settings | Add-Member -NotePropertyName Macast_Renderer -NotePropertyValue $selectedRenderer -Force
    $settings | Add-Member -NotePropertyName LanercOutputMode -NotePropertyValue 'local' -Force
    $settings | Add-Member -NotePropertyName LanercLocalPlayer -NotePropertyValue $(if ($potPlayer) { 'potplayer' } else { 'mpv' }) -Force
    if (-not $settings.PSObject.Properties['LanercTVAudio']) {
        $settings | Add-Member -NotePropertyName LanercTVAudio -NotePropertyValue 'tv'
    }
    if (-not $settings.PSObject.Properties['LanercAudioDelay']) {
        $settings | Add-Member -NotePropertyName LanercAudioDelay -NotePropertyValue 2.0
    }
    if (-not $settings.PSObject.Properties['LanercAutoSync']) {
        $settings | Add-Member -NotePropertyName LanercAutoSync -NotePropertyValue $true
    }
    if (-not $settings.PSObject.Properties['LanercControlPort']) {
        $settings | Add-Member -NotePropertyName LanercControlPort -NotePropertyValue 4380
    }
    if (-not $settings.PSObject.Properties['LanercTVIP']) {
        $settings | Add-Member -NotePropertyName LanercTVIP -NotePropertyValue ''
    }
    if (-not $settings.PSObject.Properties['LanercTVLocation']) {
        $settings | Add-Member -NotePropertyName LanercTVLocation -NotePropertyValue ''
    }
    if (-not $settings.PSObject.Properties['LanercFFmpegPath'] -or -not $settings.LanercFFmpegPath) {
        $settings | Add-Member -NotePropertyName LanercFFmpegPath -NotePropertyValue $(if ($ffmpeg) { $ffmpeg } else { '' }) -Force
    }
    if (-not $settings.PSObject.Properties['LanercRelayPort']) {
        $settings | Add-Member -NotePropertyName LanercRelayPort -NotePropertyValue 0
    }
    $json = $settings | ConvertTo-Json -Depth 10 -EscapeHandling EscapeNonAscii
    [IO.File]::WriteAllText($settingsPath, $json, [Text.UTF8Encoding]::new($false))
}

Write-Host "Installed renderers in: $rendererDir"
Write-Host "Macast renderer selected: $selectedRenderer"
Write-Host 'Control panel: http://127.0.0.1:4380/'
if ($ffmpeg) {
    Write-Host "TV relay FFmpeg: $ffmpeg"
} else {
    Write-Warning 'Lanerc TV Renderer requires ffmpeg.exe. Install FFmpeg or set LanercFFmpegPath.'
}
Write-Host 'Exit Macast completely and start it again to load the plugin.'
