$ErrorActionPreference = 'Stop'

function ConvertTo-AsciiJson {
    param([Parameter(Mandatory = $true)]$InputObject)
    $json = $InputObject | ConvertTo-Json -Depth 10
    $builder = [Text.StringBuilder]::new()
    foreach ($character in $json.ToCharArray()) {
        $code = [int]$character
        if ($code -gt 127) { [void]$builder.Append(('\u{0:x4}' -f $code)) }
        else { [void]$builder.Append($character) }
    }
    return $builder.ToString()
}

$running = Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -like 'Macast*' }
if ($running) { throw 'Macast 正在运行。请从托盘完全退出 Macast 后重新卸载。' }

$macastDir = Join-Path $env:LOCALAPPDATA 'xfangfang\Macast'
$rendererDir = Join-Path $macastDir 'renderer'
$settingsPath = Join-Path $macastDir 'macast_setting.json'

foreach ($name in @('lanerc_proxy.py', 'lanerc_potplayer.py', 'lanerc_tv.py', 'lanerc_pro.py', 'lanerc_pro.html')) {
    $path = Join-Path $rendererDir $name
    if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force }
}
$assetDir = Join-Path $rendererDir 'lanerc_assets'
if (Test-Path -LiteralPath $assetDir) { Remove-Item -LiteralPath $assetDir -Recurse -Force }

if (Test-Path -LiteralPath $settingsPath) {
    $settings = Get-Content -Raw -LiteralPath $settingsPath | ConvertFrom-Json
    if ($settings.Macast_Renderer -in @('Lanerc Cast', 'Lanerc Cast Pro', 'Lanerc PotPlayer Renderer', 'Lanerc MPV Renderer', 'Lanerc TV Renderer')) {
        $settings.Macast_Renderer = 'MPV Renderer'
    }
    foreach ($name in @('LanercOutputMode', 'LanercLocalPlayer', 'LanercTVAudio', 'LanercAudioDelay', 'LanercAutoSync', 'LanercControlPort', 'LanercTVIP', 'LanercTVLocation', 'LanercFFmpegPath', 'LanercRelayPort')) {
        $settings.PSObject.Properties.Remove($name)
    }
    [IO.File]::WriteAllText(
        $settingsPath,
        (ConvertTo-AsciiJson $settings),
        [Text.UTF8Encoding]::new($false)
    )
}

Write-Host 'Lanerc Cast 已卸载。重新启动 Macast 后生效。' -ForegroundColor Green
