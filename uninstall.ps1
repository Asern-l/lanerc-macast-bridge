$ErrorActionPreference = 'Stop'

$macastDir = Join-Path $env:LOCALAPPDATA 'xfangfang\Macast'
$rendererDir = Join-Path $macastDir 'renderer'
$settingsPath = Join-Path $macastDir 'macast_setting.json'

foreach ($name in @('lanerc_proxy.py', 'lanerc_potplayer.py', 'lanerc_tv.py', 'lanerc_pro.py', 'lanerc_pro.html')) {
    $path = Join-Path $rendererDir $name
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Force
    }
}

if (Test-Path -LiteralPath $settingsPath) {
    $settings = Get-Content -Raw $settingsPath | ConvertFrom-Json
    if ($settings.Macast_Renderer -in @('Lanerc PotPlayer Renderer', 'Lanerc MPV Renderer', 'Lanerc TV Renderer', 'Lanerc Cast Pro')) {
        $settings.Macast_Renderer = 'MPV Renderer'
        $json = $settings | ConvertTo-Json -Depth 10 -EscapeHandling EscapeNonAscii
        [IO.File]::WriteAllText($settingsPath, $json, [Text.UTF8Encoding]::new($false))
    }
}

Write-Host 'Lanerc renderer plugins removed.'
Write-Host 'Exit Macast completely and start it again.'
