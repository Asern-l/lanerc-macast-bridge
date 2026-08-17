$ErrorActionPreference = 'Stop'

function ConvertTo-AsciiJson {
    param([Parameter(Mandatory = $true)]$InputObject)
    $json = $InputObject | ConvertTo-Json -Depth 10
    $builder = [Text.StringBuilder]::new()
    foreach ($character in $json.ToCharArray()) {
        $code = [int]$character
        if ($code -gt 127) {
            [void]$builder.Append(('\u{0:x4}' -f $code))
        } else {
            [void]$builder.Append($character)
        }
    }
    return $builder.ToString()
}

function Add-DefaultSetting {
    param($Settings, [string]$Name, $Value)
    if (-not $Settings.PSObject.Properties[$Name]) {
        $Settings | Add-Member -NotePropertyName $Name -NotePropertyValue $Value
    }
}

$running = Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -like 'Macast*' }
if ($running) {
    throw 'Macast 正在运行。请从托盘完全退出 Macast 后重新安装。'
}

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$macastDir = Join-Path $env:LOCALAPPDATA 'xfangfang\Macast'
$rendererDir = Join-Path $macastDir 'renderer'
$assetDir = Join-Path $rendererDir 'lanerc_assets'
$settingsPath = Join-Path $macastDir 'macast_setting.json'
$backupDir = Join-Path $macastDir 'backup'

New-Item -ItemType Directory -Force $rendererDir, $assetDir, $backupDir | Out-Null

foreach ($name in @('lanerc_proxy.py', 'lanerc_potplayer.py', 'lanerc_tv.py', 'lanerc_pro.py', 'lanerc_pro.html')) {
    Copy-Item -Force (Join-Path $projectDir $name) (Join-Path $rendererDir $name)
}
Copy-Item -Force (Join-Path $projectDir 'lanerc_assets\*') $assetDir

$potPlayerCandidates = @(
    'D:\PotPlayer\PotPlayerMini64.exe',
    'D:\PotPlayer\PotPlayerMini.exe',
    'C:\Program Files\DAUM\PotPlayer\PotPlayerMini64.exe',
    'C:\Program Files (x86)\DAUM\PotPlayer\PotPlayerMini.exe',
    'C:\Program Files\PotPlayer\PotPlayerMini64.exe'
)
foreach ($registryPath in @('HKCU:\Software\DAUM\PotPlayer64', 'HKCU:\Software\DAUM\PotPlayer')) {
    try {
        $registered = (Get-ItemProperty -LiteralPath $registryPath -Name ProgramPath -ErrorAction Stop).ProgramPath
        if ($registered) { $potPlayerCandidates = @($registered) + $potPlayerCandidates }
    } catch { }
}
$potPlayer = $potPlayerCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1

$ffmpegCandidates = @(
    'D:\Macast\tools\ffmpeg\bin\ffmpeg.exe',
    'D:\ffmpeg\bin\ffmpeg.exe',
    'C:\ffmpeg\bin\ffmpeg.exe',
    (Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Links\ffmpeg.exe')
)
$ffmpegCommand = Get-Command ffmpeg.exe -ErrorAction SilentlyContinue
if ($ffmpegCommand) { $ffmpegCandidates = @($ffmpegCommand.Source) + $ffmpegCandidates }
$ffmpeg = $ffmpegCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1

if (Test-Path -LiteralPath $settingsPath) {
    $timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    Copy-Item -LiteralPath $settingsPath -Destination (Join-Path $backupDir "macast_setting-$timestamp.json")
    $settings = Get-Content -Raw -LiteralPath $settingsPath | ConvertFrom-Json
} else {
    $settings = [pscustomobject]@{}
}

$settings | Add-Member -NotePropertyName Macast_Renderer -NotePropertyValue 'Lanerc Cast' -Force
Add-DefaultSetting $settings 'LanercOutputMode' 'local'
Add-DefaultSetting $settings 'LanercLocalPlayer' $(if ($potPlayer) { 'potplayer' } else { 'mpv' })
Add-DefaultSetting $settings 'LanercTVAudio' 'tv'
Add-DefaultSetting $settings 'LanercAudioDelay' 2.0
Add-DefaultSetting $settings 'LanercAutoSync' $false
Add-DefaultSetting $settings 'LanercControlPort' 4380
Add-DefaultSetting $settings 'LanercTVIP' ''
Add-DefaultSetting $settings 'LanercTVLocation' ''
Add-DefaultSetting $settings 'LanercFFmpegPath' $(if ($ffmpeg) { $ffmpeg } else { '' })
Add-DefaultSetting $settings 'LanercRelayPort' 0

$json = ConvertTo-AsciiJson $settings
[IO.File]::WriteAllText($settingsPath, $json, [Text.UTF8Encoding]::new($false))

Write-Host ''
Write-Host 'Lanerc Cast 2.0 安装完成' -ForegroundColor Green
Write-Host "  插件目录：$rendererDir"
Write-Host '  控制中心：http://127.0.0.1:4380/'
Write-Host "  本机播放器：$(if ($potPlayer) { 'PotPlayer' } else { 'Macast 内置播放器' })"
Write-Host "  电视转码：$(if ($ffmpeg) { 'FFmpeg 已就绪' } else { 'FFmpeg 未安装' })"
Write-Host ''
Write-Host '现在可以重新启动 Macast。'
